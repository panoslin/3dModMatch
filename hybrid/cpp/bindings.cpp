// bindings.cpp - Hybrid Python + C++17 Shoe-Last Matcher (v0.5)
// 依赖：Open3D >= 0.18, pybind11, Eigen3
// 功能：ICP/RANSAC 配准、Chamfer、采样式 SDF、体素窄带 SDF（形式化复核）
//      最薄点定位、薄壁段聚类与区域标注、剖切线段、批量并行接口

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include <open3d/Open3D.h>
#include <open3d/t/geometry/TriangleMesh.h>
#include <open3d/t/geometry/RaycastingScene.h>

#include <Eigen/Dense>
#include <numeric>
#include <optional>
#include <cmath>

#ifdef HYBRID_WITH_OPENMP
  #include <omp.h>
#endif

namespace py = pybind11;
using namespace py::literals;
using namespace open3d;

// ----------------------------- 工具函数 -----------------------------

static std::shared_ptr<geometry::TriangleMesh>
mesh_from_np(py::array_t<double> verts, py::array_t<int> faces) {
    auto bufV = verts.request();
    if (bufV.ndim != 2 || bufV.shape[1] != 3) {
        throw std::runtime_error("verts must be (N,3) float64");
    }
    auto m = std::make_shared<geometry::TriangleMesh>();
    m->vertices_.resize(bufV.shape[0]);

    const double* pV = static_cast<const double*>(bufV.ptr);
    for (ssize_t i = 0; i < bufV.shape[0]; ++i) {
        m->vertices_[i] = Eigen::Vector3d(pV[3 * i + 0], pV[3 * i + 1], pV[3 * i + 2]);
    }

    if (faces.size() > 0) {
        auto bufF = faces.request();
        if (bufF.ndim != 2 || bufF.shape[1] != 3) {
            throw std::runtime_error("faces must be (M,3) int32");
        }
        m->triangles_.resize(bufF.shape[0]);
        const int* pF = static_cast<const int*>(bufF.ptr);
        for (ssize_t i = 0; i < bufF.shape[0]; ++i) {
            m->triangles_[i] = Eigen::Vector3i(pF[3 * i + 0], pF[3 * i + 1], pF[3 * i + 2]);
        }
    }

    if (!m->triangles_.empty()) {
        m->RemoveDegenerateTriangles();
        m->RemoveDuplicatedTriangles();
    }
    m->RemoveDuplicatedVertices();
    m->RemoveUnreferencedVertices();
    return m;
}

static std::shared_ptr<geometry::PointCloud>
sample_pcd(geometry::TriangleMesh &m, size_t n) {
    if (m.triangles_.empty()) {
        // 如果没有面，则用顶点构建点云
        auto p = std::make_shared<geometry::PointCloud>();
        p->points_ = m.vertices_;
        return p;
    }
    return m.SamplePointsUniformly(n);
}

static void est_normals(geometry::PointCloud &pcd, double radius) {
    pcd.EstimateNormals(geometry::KDTreeSearchParamHybrid(radius, 60));
    pcd.NormalizeNormals();
}

static Eigen::Matrix4d ransac(geometry::PointCloud &src, geometry::PointCloud &tgt,
                              double radius, double voxel) {
    est_normals(src, radius);
    est_normals(tgt, radius);

    auto fsrc = pipelines::registration::ComputeFPFHFeature(
        src, geometry::KDTreeSearchParamHybrid(radius, 100));
    auto ftgt = pipelines::registration::ComputeFPFHFeature(
        tgt, geometry::KDTreeSearchParamHybrid(radius, 100));

    const double thr = voxel * 3.0;
    std::vector<std::reference_wrapper<const pipelines::registration::CorrespondenceChecker>> checkers;
    auto checker = std::make_shared<pipelines::registration::CorrespondenceCheckerBasedOnDistance>(thr);
    checkers.push_back(*checker);
    auto result = pipelines::registration::RegistrationRANSACBasedOnFeatureMatching(
        src, tgt, *fsrc, *ftgt, true, thr,
        pipelines::registration::TransformationEstimationPointToPoint(false), 4,
        checkers,
        pipelines::registration::RANSACConvergenceCriteria(8000, 1000));
    return result.transformation_;
}

static Eigen::Matrix4d icp(geometry::PointCloud &src, geometry::PointCloud &tgt,
                           const Eigen::Matrix4d &init, double thr) {
    est_normals(tgt, thr);
    auto result = pipelines::registration::RegistrationICP(
        src, tgt, thr, init,
        pipelines::registration::TransformationEstimationPointToPlane());
    return result.transformation_;
}

static double chamfer(const geometry::PointCloud &A, const geometry::PointCloud &B) {
    geometry::KDTreeFlann kdb(B), kda(A);
    double sum = 0;
    size_t n = 0;
    std::vector<int> idx(1);
    std::vector<double> dist(1);

    for (const auto &p : A.points_) {
        if (kdb.SearchKNN(p, 1, idx, dist)) {
            sum += std::sqrt(dist[0]);
            ++n;
        }
    }
    for (const auto &p : B.points_) {
        if (kda.SearchKNN(p, 1, idx, dist)) {
            sum += std::sqrt(dist[0]);
            ++n;
        }
    }
    return n ? sum / n : 1e9;
}

// ----------------------------- 粗特征 -----------------------------

struct CoarseFeat {
    double volume{0};
    double area{0};
    Eigen::Vector3d extents{0, 0, 0};
    std::vector<float> hist; // 8 x 16 方向直方图
};

static CoarseFeat coarse_features_from_mesh(const geometry::TriangleMesh &m) {
    CoarseFeat f{};
    auto bb = m.GetAxisAlignedBoundingBox();
    f.extents = bb.GetExtent();
    f.area = m.GetSurfaceArea();

    double vol = 0.0; // signed volume by tetra origin
    for (auto &tri : m.triangles_) {
        const auto &a = m.vertices_[tri(0)];
        const auto &b = m.vertices_[tri(1)];
        const auto &c = m.vertices_[tri(2)];
        vol += a.dot(b.cross(c));
    }
    f.volume = std::abs(vol / 6.0);

    const int B1 = 8, B2 = 16;
    f.hist.assign(B1 * B2, 0.f);
    for (auto &tri : m.triangles_) {
        const auto &a = m.vertices_[tri(0)];
        const auto &b = m.vertices_[tri(1)];
        const auto &c = m.vertices_[tri(2)];
        Eigen::Vector3d n = (b - a).cross(c - a);
        double len = n.norm();
        if (len < 1e-12) continue;
        n /= len;
        double theta = std::acos(std::max(-1.0, std::min(1.0, n.z())));
        double phi = std::atan2(n.y(), n.x());
        if (phi < 0) phi += 2 * M_PI;
        int i = std::min(B1 - 1, int(theta / M_PI * B1));
        int j = std::min(B2 - 1, int(phi / (2 * M_PI) * B2));
        f.hist[i * B2 + j] += 1.f;
    }
    float s = 0.f;
    for (float v : f.hist) s += v;
    if (s > 0) for (float &v : f.hist) v /= s;
    return f;
}

py::dict coarse_features(py::array_t<double> v, py::array_t<int> f) {
    auto m = mesh_from_np(v, f);
    auto cf = coarse_features_from_mesh(*m);
    py::dict out;
    out["volume"] = cf.volume;
    out["area"] = cf.area;
    out["extents"] = py::make_tuple(cf.extents.x(), cf.extents.y(), cf.extents.z());
    out["normal_hist"] = cf.hist;
    return out;
}

// ----------------------------- 对齐 -----------------------------

py::dict align_icp(py::array_t<double> v_src, py::array_t<int> f_src,
                   py::array_t<double> v_tgt, py::array_t<int> f_tgt,
                   double voxel, double fpfh_radius, double icp_thr) {
    auto mS = mesh_from_np(v_src, f_src);
    auto mT = mesh_from_np(v_tgt, f_tgt);
    auto pS = sample_pcd(*mS, 50000)->VoxelDownSample(voxel);
    auto pT = sample_pcd(*mT, 50000)->VoxelDownSample(voxel);

    Eigen::Matrix4d T0 = ransac(*pS, *pT, fpfh_radius, voxel);
    Eigen::Matrix4d T = icp(*pS, *pT, T0, icp_thr);

    auto S_aligned = *mS;
    S_aligned.Transform(T);
    auto pSa = sample_pcd(S_aligned, 20000);
    auto pTb = sample_pcd(*mT, 20000);
    double ch = chamfer(*pSa, *pTb);

    py::array_t<double> Tnp({4, 4});
    auto r = Tnp.mutable_unchecked<2>();
    for (int i = 0; i < 4; ++i) for (int j = 0; j < 4; ++j) r(i, j) = T(i, j);

    py::dict out;
    out["T"] = Tnp;
    out["chamfer"] = ch;
    return out;
}

py::dict align_icp_with_mirror(py::array_t<double> v_src, py::array_t<int> f_src,
                               py::array_t<double> v_tgt, py::array_t<int> f_tgt,
                               double voxel, double fpfh_radius, double icp_thr) {
    auto mS = mesh_from_np(v_src, f_src);
    auto mT = mesh_from_np(v_tgt, f_tgt);
    auto pT = sample_pcd(*mT, 50000)->VoxelDownSample(voxel);

    // 原始
    auto pS0 = sample_pcd(*mS, 50000)->VoxelDownSample(voxel);
    Eigen::Matrix4d T0 = icp(*pS0, *pT, ransac(*pS0, *pT, fpfh_radius, voxel), icp_thr);
    auto Sa = *mS; Sa.Transform(T0);
    double ch0 = chamfer(*sample_pcd(Sa, 20000), *sample_pcd(*mT, 20000));

    // 镜像（YZ 平面，x -> -x）
    Eigen::Matrix4d M = Eigen::Matrix4d::Identity(); M(0, 0) = -1.0;
    auto Sm = *mS; Sm.Transform(M);
    auto pSm = sample_pcd(Sm, 50000)->VoxelDownSample(voxel);
    Eigen::Matrix4d Tm = icp(*pSm, *pT, ransac(*pSm, *pT, fpfh_radius, voxel), icp_thr);
    auto Sb = Sm; Sb.Transform(Tm);
    double chm = chamfer(*sample_pcd(Sb, 20000), *sample_pcd(*mT, 20000));

    Eigen::Matrix4d Tbest = (chm < ch0 ? (Tm * M) : T0);
    bool mirrored = (chm < ch0);
    double ch = std::min(ch0, chm);

    py::array_t<double> Tnp({4, 4});
    auto r = Tnp.mutable_unchecked<2>();
    for (int i = 0; i < 4; ++i) for (int j = 0; j < 4; ++j) r(i, j) = Tbest(i, j);

    return py::dict("T"_a = Tnp, "chamfer"_a = ch, "mirrored"_a = mirrored);
}

// ----------------------------- 采样式 SDF 余量 -----------------------------

py::dict clearance_sampling(py::array_t<double> v_tgt, py::array_t<int> f_tgt,
                            py::array_t<double> v_cand, py::array_t<int> f_cand,
                            double clearance, double safety_delta, size_t samples) {
    auto mT = mesh_from_np(v_tgt, f_tgt);
    auto mC = mesh_from_np(v_cand, f_cand);
    auto pts = mT->SamplePointsUniformly(samples);

    t::geometry::TriangleMesh tmC = t::geometry::TriangleMesh::FromLegacy(*mC);
    t::geometry::RaycastingScene scene; scene.AddTriangles(tmC);

    std::vector<float> buf; buf.reserve(pts->points_.size() * 3);
    for (auto &p : pts->points_) { buf.push_back((float)p.x()); buf.push_back((float)p.y()); buf.push_back((float)p.z()); }
    core::Tensor q(buf, {(int64_t)pts->points_.size(), 3}, core::Float32);

    auto sdist = scene.ComputeSignedDistance(q); // negative inside
    auto inside = scene.ComputeOccupancy(q);

    std::vector<float> sdv(sdist.GetDataPtr<float>(), sdist.GetDataPtr<float>() + sdist.NumElements());
    std::vector<float> inv(inside.GetDataPtr<float>(), inside.GetDataPtr<float>() + inside.NumElements());

    std::vector<double> inner; inner.reserve(sdv.size()); size_t inside_cnt = 0;
    for (size_t i = 0; i < sdv.size(); ++i) {
        // inv[i] > 0.5f means the point is INSIDE the candidate mesh
        // sdv[i] is negative when inside, positive when outside
        // For clearance, we want the absolute distance when inside
        if (inv[i] > 0.5f) { 
            inside_cnt++; 
            // Use absolute value of signed distance as clearance
            inner.push_back(std::abs((double)sdv[i])); 
        }
    }
    double inside_ratio = (double)inside_cnt / std::max<size_t>(1, sdv.size());

    double min_c = 0, mean_c = 0, p01 = 0; bool pass = false;
    if (!inner.empty()) {
        std::sort(inner.begin(), inner.end());
        min_c = inner.front();  // Minimum clearance (smallest distance from target to candidate interior)
        mean_c = std::accumulate(inner.begin(), inner.end(), 0.0) / inner.size();
        size_t k = (size_t)std::floor(0.01 * inner.size());
        if (k >= inner.size()) k = inner.size() - 1;
        p01 = inner[k];
        // Pass only if ALL points are inside (inside_ratio == 1.0) AND minimum clearance is sufficient
        pass = (inside_ratio >= 0.999) && (min_c >= clearance);  // Allow 0.1% tolerance for numerical errors
    }
    return py::dict("pass"_a = pass, "min_clearance"_a = min_c, "mean_clearance"_a = mean_c,
                    "p01_clearance"_a = p01, "inside_ratio"_a = inside_ratio);
}

// ----------------------------- 批量并行：对齐 + 采样 SDF -----------------------------

py::list batch_align_and_check(py::array_t<double> v_tgt, py::array_t<int> f_tgt,
                               std::vector<py::array_t<double>> V_cands,
                               std::vector<py::array_t<int>> F_cands,
                               double voxel, double fpfh_radius, double icp_thr,
                               double clearance, double safety_delta, size_t samples,
                               int threads) {
    auto mT = mesh_from_np(v_tgt, f_tgt);

    py::gil_scoped_release nogil;
#ifdef HYBRID_WITH_OPENMP
    if (threads > 0) omp_set_num_threads(threads);
#endif

    std::vector<py::dict> outs(V_cands.size());

#pragma omp parallel for schedule(dynamic)
    for (int i = 0; i < (int)V_cands.size(); ++i) {
        try {
            auto mS = mesh_from_np(V_cands[i], F_cands[i]);

            auto pT = sample_pcd(*mT, 50000);
            auto pS0 = sample_pcd(*mS, 50000);
            auto dsT = pT->VoxelDownSample(voxel);
            auto dsS = pS0->VoxelDownSample(voxel);

            Eigen::Matrix4d T0 = icp(*dsS, *dsT, ransac(*dsS, *dsT, fpfh_radius, voxel), icp_thr);
            auto Sa = *mS; Sa.Transform(T0);
            double ch0 = chamfer(*sample_pcd(Sa, 20000), *sample_pcd(*mT, 20000));

            Eigen::Matrix4d M = Eigen::Matrix4d::Identity(); M(0, 0) = -1.0;
            auto Sm = *mS; Sm.Transform(M);
            auto dsSm = sample_pcd(Sm, 50000)->VoxelDownSample(voxel);
            Eigen::Matrix4d Tm = icp(*dsSm, *dsT, ransac(*dsSm, *dsT, fpfh_radius, voxel), icp_thr);
            auto Sb = Sm; Sb.Transform(Tm);
            double chm = chamfer(*sample_pcd(Sb, 20000), *sample_pcd(*mT, 20000));

            bool mirrored = (chm < ch0);
            Eigen::Matrix4d Tbest = mirrored ? (Tm * M) : T0;

            auto Saligned = *mS; Saligned.Transform(Tbest);

            // clearance sampling
            t::geometry::TriangleMesh tmC = t::geometry::TriangleMesh::FromLegacy(Saligned);
            t::geometry::RaycastingScene scene; scene.AddTriangles(tmC);
            auto pts = mT->SamplePointsUniformly(samples);
            std::vector<float> buf; buf.reserve(pts->points_.size() * 3);
            for (auto &p : pts->points_) { buf.push_back((float)p.x()); buf.push_back((float)p.y()); buf.push_back((float)p.z()); }
            core::Tensor q(buf, {(int64_t)pts->points_.size(), 3}, core::Float32);
            auto sdist = scene.ComputeSignedDistance(q);
            auto inside = scene.ComputeOccupancy(q);

            std::vector<float> sdv(sdist.GetDataPtr<float>(), sdist.GetDataPtr<float>() + sdist.NumElements());
            std::vector<float> inv(inside.GetDataPtr<float>(), inside.GetDataPtr<float>() + inside.NumElements());
            std::vector<double> inner; inner.reserve(sdv.size()); size_t inside_cnt = 0;
            for (size_t k = 0; k < sdv.size(); ++k) { if (inv[k] > 0.5f) { inside_cnt++; inner.push_back(-(double)sdv[k]); } }
            double min_c = 0, mean_c = 0, p01 = 0; bool pass = false;
            if (!inner.empty()) {
                std::sort(inner.begin(), inner.end());
                min_c = inner.front();
                mean_c = std::accumulate(inner.begin(), inner.end(), 0.0) / inner.size();
                size_t kk = (size_t)std::floor(0.01 * inner.size());
                if (kk >= inner.size()) kk = inner.size() - 1;
                p01 = inner[kk];
                pass = (min_c >= (clearance + safety_delta));
            }

            py::array_t<double> Tnp({4, 4});
            auto r = Tnp.mutable_unchecked<2>();
            for (int a = 0; a < 4; ++a) for (int b = 0; b < 4; ++b) r(a, b) = Tbest(a, b);
            outs[i] = py::dict("mirrored"_a = mirrored, "chamfer"_a = std::min(ch0, chm),
                               "min_clearance"_a = min_c, "mean_clearance"_a = mean_c,
                               "p01_clearance"_a = p01, "pass"_a = pass, "T"_a = Tnp);
        } catch (const std::exception &e) {
            outs[i] = py::dict("error"_a = e.what());
        }
    }

    py::gil_scoped_acquire gil;
    py::list L; for (auto &o : outs) L.append(o);
    return L;
}

// ----------------------------- 体素窄带 SDF（形式化复核） -----------------------------

py::dict clearance_sdf_volume(py::array_t<double> v_tgt, py::array_t<int> f_tgt,
                              py::array_t<double> v_cand, py::array_t<int> f_cand,
                              double clearance, double voxel, double band_mm, int threads) {
    auto mT = mesh_from_np(v_tgt, f_tgt);
    auto mC = mesh_from_np(v_cand, f_cand);

    t::geometry::TriangleMesh tT = t::geometry::TriangleMesh::FromLegacy(*mT);
    t::geometry::TriangleMesh tC = t::geometry::TriangleMesh::FromLegacy(*mC);
    t::geometry::RaycastingScene sceneT; sceneT.AddTriangles(tT);
    t::geometry::RaycastingScene sceneC; sceneC.AddTriangles(tC);

    auto bb = mT->GetAxisAlignedBoundingBox();
    Eigen::Vector3d min = bb.min_bound_ - Eigen::Vector3d::Constant(band_mm);
    Eigen::Vector3d max = bb.max_bound_ + Eigen::Vector3d::Constant(band_mm);

    Eigen::Vector3i dims;
    for (int i = 0; i < 3; ++i) dims[i] = std::max(1, (int)std::ceil((max[i] - min[i]) / voxel));

    const int64_t NX = dims[0], NY = dims[1], NZ = dims[2];
    std::vector<float> pts; pts.reserve((size_t)NX * NY * NZ * 3);
    for (int64_t ix = 0; ix < NX; ++ix) {
        double x = min.x() + (ix + 0.5) * voxel;
        for (int64_t iy = 0; iy < NY; ++iy) {
            double y = min.y() + (iy + 0.5) * voxel;
            for (int64_t iz = 0; iz < NZ; ++iz) {
                double z = min.z() + (iz + 0.5) * voxel;
                pts.push_back((float)x); pts.push_back((float)y); pts.push_back((float)z);
            }
        }
    }
    core::Tensor Q(pts, {(int64_t)(pts.size() / 3), 3}, core::Float32);

    auto dT = sceneT.ComputeDistance(Q); // unsigned
    std::vector<float> dTvec(dT.GetDataPtr<float>(), dT.GetDataPtr<float>() + dT.NumElements());

    std::vector<int64_t> sel_idx; sel_idx.reserve(dTvec.size() / 8);
    for (int64_t i = 0; i < (int64_t)dTvec.size(); ++i)
        if (dTvec[i] <= (float)band_mm) sel_idx.push_back(i);
    if (sel_idx.empty()) return py::dict("pass"_a = false, "reason"_a = "no samples in band");

    core::Tensor idx(sel_idx.data(), {(int64_t)sel_idx.size()}, core::Int64);
    auto Qb = Q.IndexGet({idx});

    auto sdC = sceneC.ComputeSignedDistance(Qb);
    std::vector<float> sdc(sdC.GetDataPtr<float>(), sdC.GetDataPtr<float>() + sdC.NumElements());

    double min_c = 1e18, mean_c = 0.0;
    size_t inside_cnt = 0, cnt = 0;
    for (float v : sdc) {
        if (v <= 0.f) {
            inside_cnt++;
            double c = -double(v);
            min_c = std::min(min_c, c);
            mean_c += c; cnt++;
        }
    }
    if (cnt > 0) mean_c /= cnt; else { min_c = 0.0; mean_c = 0.0; }

    double eps = 0.866 * voxel; // 误差上界（sqrt(3)/2 * g）
    bool ok = (min_c - eps >= clearance);
    py::dict out;
    out["pass"] = ok;
    out["min_clearance"] = min_c;
    out["mean_clearance"] = mean_c;
    out["voxel"] = voxel;
    out["band_mm"] = band_mm;
    out["eps"] = eps;
    out["inside_ratio"] = (double)inside_cnt / (double)sel_idx.size();
    return out;
}

py::list batch_formal_check(py::array_t<double> v_tgt, py::array_t<int> f_tgt,
                            std::vector<py::array_t<double>> V_cands,
                            std::vector<py::array_t<int>> F_cands,
                            double clearance, double voxel, double band_mm, int threads) {
    py::list out;
    for (size_t i = 0; i < V_cands.size(); ++i) {
        try {
            out.append(clearance_sdf_volume(v_tgt, f_tgt, V_cands[i], F_cands[i],
                                            clearance, voxel, band_mm, threads));
        } catch (const std::exception &e) {
            out.append(py::dict("pass"_a = false, "reason"_a = e.what()));
        }
    }
    return out;
}

// ----------------------------- 最薄点定位 -----------------------------

py::dict min_clearance_point(py::array_t<double> v_tgt, py::array_t<int> f_tgt,
                             py::array_t<double> v_cand, py::array_t<int> f_cand) {
    auto mT = mesh_from_np(v_tgt, f_tgt);
    auto mC = mesh_from_np(v_cand, f_cand);
    t::geometry::TriangleMesh tC = t::geometry::TriangleMesh::FromLegacy(*mC);
    t::geometry::RaycastingScene scene; scene.AddTriangles(tC);

    std::vector<float> buf; buf.reserve(mT->vertices_.size() * 3);
    for (const auto &p : mT->vertices_) buf.insert(buf.end(), {(float)p.x(), (float)p.y(), (float)p.z()});
    core::Tensor Q(buf, {(int64_t)mT->vertices_.size(), 3}, core::Float32);

    auto sdist = scene.ComputeSignedDistance(Q); // neg inside
    auto hit   = scene.ComputeClosestPoints(Q);
    auto hpos  = hit["points"]; // Nx3

    const float *sd = sdist.GetDataPtr<float>();
    const float *hp = static_cast<const float*>(hpos.GetDataPtr());

    double min_c = 1e18; int64_t idx_min = -1; size_t N = (size_t)mT->vertices_.size();
    for (size_t i = 0; i < N; ++i) {
        float v = sd[i];
        if (v <= 0.f) {
            double c = -double(v);
            if (c < min_c) { min_c = c; idx_min = (int64_t)i; }
        }
    }
    if (idx_min < 0) return py::dict("found"_a = false);

    Eigen::Vector3d pt = mT->vertices_[(size_t)idx_min];
    Eigen::Vector3d pc(hp[3 * idx_min + 0], hp[3 * idx_min + 1], hp[3 * idx_min + 2]);

    py::dict out;
    out["found"] = true;
    out["min_clearance"] = min_c;
    out["p_target"] = py::make_tuple(pt.x(), pt.y(), pt.z());
    out["p_candidate"] = py::make_tuple(pc.x(), pc.y(), pc.z());
    out["index"] = idx_min;
    return out;
}

// ----------------------------- 剖切线段 -----------------------------

py::dict mesh_section(py::array_t<double> v, py::array_t<int> f,
                      py::array_t<double> p0, py::array_t<double> nrm) {
    auto m = mesh_from_np(v, f);
    auto P0buf = p0.request();
    auto Nbuf  = nrm.request();
    if (P0buf.size != 3 || Nbuf.size != 3) throw std::runtime_error("p0, n must be len=3 arrays");
    double P0x = ((double*)P0buf.ptr)[0], P0y = ((double*)P0buf.ptr)[1], P0z = ((double*)P0buf.ptr)[2];
    double Nx = ((double*)Nbuf.ptr)[0], Ny = ((double*)Nbuf.ptr)[1], Nz = ((double*)Nbuf.ptr)[2];
    Eigen::Vector3d P0(P0x, P0y, P0z), N(Nx, Ny, Nz); N.normalize();

    auto sgn = [&](const Eigen::Vector3d &x) { return (N.dot(x - P0)); };

    std::vector<std::array<double, 6>> segs;
    segs.reserve(m->triangles_.size() / 10 + 1);

    for (const auto &tri : m->triangles_) {
        Eigen::Vector3d a = m->vertices_[tri(0)];
        Eigen::Vector3d b = m->vertices_[tri(1)];
        Eigen::Vector3d c = m->vertices_[tri(2)];
        double da = sgn(a), db = sgn(b), dc = sgn(c);

        int pos = (da > 0) + (db > 0) + (dc > 0);
        int neg = (da < 0) + (db < 0) + (dc < 0);
        if (pos == 3 || neg == 3) continue;

        auto cut = [&](const Eigen::Vector3d &P, double dP,
                       const Eigen::Vector3d &Q, double dQ, Eigen::Vector3d &X) {
            double t = dP / (dP - dQ);
            X = P + t * (Q - P);
        };

        std::vector<Eigen::Vector3d> pts; pts.reserve(2);
        auto proc = [&](const Eigen::Vector3d &P, double dP, const Eigen::Vector3d &Q, double dQ) {
            if ((dP > 0 && dQ < 0) || (dP < 0 && dQ > 0)) {
                Eigen::Vector3d X; cut(P, dP, Q, dQ, X); pts.push_back(X);
            }
        };
        proc(a, da, b, db); proc(b, db, c, dc); proc(c, dc, a, da);
        if (pts.size() == 2) {
            segs.push_back({pts[0].x(), pts[0].y(), pts[0].z(),
                            pts[1].x(), pts[1].y(), pts[1].z()});
        }
    }

    py::array_t<double> A({(ssize_t)segs.size(), (ssize_t)6});
    auto w = A.mutable_unchecked<2>();
    for (ssize_t i = 0; i < (ssize_t)segs.size(); ++i)
        for (int j = 0; j < 6; ++j) w(i, j) = segs[i][j];
    return py::dict("segments"_a = A);
}

// ----------------------------- 薄壁段聚类与区域标注 -----------------------------

py::list thin_regions(py::array_t<double> v_tgt, py::array_t<int> f_tgt,
                      py::array_t<double> v_cand, py::array_t<int> f_cand,
                      double thr_mm, double radius_mm) {
    auto mT = mesh_from_np(v_tgt, f_tgt);
    auto mC = mesh_from_np(v_cand, f_cand);
    t::geometry::TriangleMesh tC = t::geometry::TriangleMesh::FromLegacy(*mC);
    t::geometry::RaycastingScene scene; scene.AddTriangles(tC);

    // 计算每个目标顶点 clearance
    std::vector<float> buf; buf.reserve(mT->vertices_.size() * 3);
    for (const auto &p : mT->vertices_) buf.insert(buf.end(), {(float)p.x(), (float)p.y(), (float)p.z()});
    core::Tensor Q(buf, {(int64_t)mT->vertices_.size(), 3}, core::Float32);
    auto sdist = scene.ComputeSignedDistance(Q);
    const float *sd = sdist.GetDataPtr<float>();
    size_t N = mT->vertices_.size();

    // 选薄壁点
    std::vector<int> idxs; idxs.reserve(N);
    for (size_t i = 0; i < N; ++i)
        if (sd[i] <= 0.f && (-double(sd[i]) < thr_mm)) idxs.push_back((int)i);
    if (idxs.empty()) return py::list();

    // 半径聚类（简易贪心）
    std::vector<int> label(N, -1);
    int cid = 0;
    double r2 = radius_mm * radius_mm;
    for (int i : idxs) {
        if (label[i] != -1) continue;
        label[i] = cid;
        // 扩张：线性扫描（足够快；需要更快可改 KDTree）
        bool grown = true;
        while (grown) {
            grown = false;
            for (int j : idxs) if (label[j] == -1) {
                const auto &pi = mT->vertices_[i];
                const auto &pj = mT->vertices_[j];
                if ((pi - pj).squaredNorm() <= r2) { label[j] = cid; grown = true; }
            }
        }
        cid++;
    }

    // 汇总
    py::list regions;
    regions.attr("reserve")(cid);
    for (int k = 0; k < cid; ++k) {
        std::vector<int> verts_k; verts_k.reserve(128);
        double min_c = 1e9;
        Eigen::Vector3d centroid = Eigen::Vector3d::Zero(); int cnt = 0;
        for (size_t i = 0; i < N; ++i) if (label[i] == k) {
            verts_k.push_back((int)i);
            double clr = -double(sd[i]);
            min_c = std::min(min_c, clr);
            centroid += mT->vertices_[i];
            cnt++;
        }
        if (cnt > 0) centroid /= cnt; else centroid.setZero();

        // 骨架：PCA 主方向的两端点
        Eigen::MatrixXd P(3, verts_k.size());
        for (size_t t = 0; t < verts_k.size(); ++t) {
            auto &v = mT->vertices_[verts_k[t]];
            P.col(t) << v.x(), v.y(), v.z();
        }
        Eigen::Vector3d mean = P.rowwise().mean();
        Eigen::MatrixXd Z = P.colwise() - mean;
        Eigen::Matrix3d C = (Z * Z.transpose()) / std::max<ptrdiff_t>(1, Z.cols());
        Eigen::SelfAdjointEigenSolver<Eigen::Matrix3d> es(C);
        Eigen::Vector3d dir = es.eigenvectors().col(2);
        std::vector<std::pair<double, int>> proj; proj.reserve(verts_k.size());
        for (size_t t = 0; t < verts_k.size(); ++t) {
            Eigen::Vector3d d = P.col(t) - mean;
            proj.emplace_back(dir.dot(d), (int)t);
        }
        std::sort(proj.begin(), proj.end());
        auto pA = P.col(proj.front().second);
        auto pB = P.col(proj.back().second);

        py::dict reg;
        reg["min_clearance"] = min_c;
        reg["centroid"] = py::make_tuple(centroid.x(), centroid.y(), centroid.z());
        reg["endpoints"] = py::make_tuple(py::make_tuple(pA.x(), pA.y(), pA.z()),
                                          py::make_tuple(pB.x(), pB.y(), pB.z()));
        reg["indices"] = verts_k; // 目标顶点索引集合
        regions.append(reg);
    }
    return regions;
}

py::list label_regions(py::array_t<double> v_tgt, py::list regions) {
    // 直接用顶点做 PCA（不需要 faces）
    auto bufV = v_tgt.request();
    if (bufV.ndim != 2 || bufV.shape[1] != 3) throw std::runtime_error("v_tgt must be (N,3)");
    size_t N = bufV.shape[0];
    const double* pV = static_cast<const double*>(bufV.ptr);

    Eigen::MatrixXd P(3, N);
    for (size_t i = 0; i < N; ++i) {
        P.col(i) << pV[3 * i + 0], pV[3 * i + 1], pV[3 * i + 2];
    }
    Eigen::Vector3d mean = P.rowwise().mean();
    Eigen::MatrixXd Z = P.colwise() - mean;
    Eigen::Matrix3d C = (Z * Z.transpose()) / std::max<ptrdiff_t>(1, Z.cols());
    Eigen::SelfAdjointEigenSolver<Eigen::Matrix3d> es(C);
    // length / width 轴
    Eigen::Vector3d aL = es.eigenvectors().col(2); // 主轴：鞋长
    Eigen::Vector3d aW = es.eigenvectors().col(1); // 次轴：宽（内外侧）

    py::list out;
    for (auto item : regions) {
        py::dict r = py::reinterpret_borrow<py::dict>(item);
        auto cen = r["centroid"];
        auto cen_list = py::cast<py::list>(cen);
        Eigen::Vector3d c(py::cast<double>(cen_list[0]), py::cast<double>(cen_list[1]), py::cast<double>(cen_list[2]));
        Eigen::Vector3d d = c - mean;
        double sL = aL.dot(d);
        double sW = aW.dot(d);
        const char *foreaft = (sL > 0 ? "toe" : "heel");
        const char *side = (sW > 0 ? "lateral" : "medial");
        r["label"] = std::string(foreaft) + "/" + side;
        out.append(r);
    }
    return out;
}

// ----------------------------- PYBIND11 模块 -----------------------------

PYBIND11_MODULE(cppcore, m) {
    m.doc() = "C++17 core for Shoe Last Matcher (v0.5)";

    // 粗特征
    m.def("coarse_features", &coarse_features, "Compute coarse descriptors");

    // 对齐
    m.def("align_icp", &align_icp, "Rigid registration (RANSAC→ICP) with chamfer",
          py::arg("v_src"), py::arg("f_src"), py::arg("v_tgt"), py::arg("f_tgt"),
          py::arg("voxel"), py::arg("fpfh_radius"), py::arg("icp_thr"));
    m.def("align_icp_with_mirror", &align_icp_with_mirror, "Registration with YZ-mirror option",
          py::arg("v_src"), py::arg("f_src"), py::arg("v_tgt"), py::arg("f_tgt"),
          py::arg("voxel"), py::arg("fpfh_radius"), py::arg("icp_thr"));

    // 采样式 SDF + 批量
    m.def("clearance_sampling", &clearance_sampling, "Sampling-based SDF clearance check",
          py::arg("v_tgt"), py::arg("f_tgt"), py::arg("v_cand"), py::arg("f_cand"),
          py::arg("clearance"), py::arg("safety_delta"), py::arg("samples") = 120000);
    m.def("batch_align_and_check", &batch_align_and_check, "Batch align+check (parallel)",
          py::arg("v_tgt"), py::arg("f_tgt"), py::arg("V_cands"), py::arg("F_cands"),
          py::arg("voxel"), py::arg("fpfh_radius"), py::arg("icp_thr"),
          py::arg("clearance"), py::arg("safety_delta"),
          py::arg("samples") = 120000, py::arg("threads") = -1);

    // 体素窄带 SDF（形式化复核）
    m.def("clearance_sdf_volume", &clearance_sdf_volume, "Voxel narrow-band SDF formal check",
          py::arg("v_tgt"), py::arg("f_tgt"), py::arg("v_cand"), py::arg("f_cand"),
          py::arg("clearance"), py::arg("voxel") = 0.30, py::arg("band_mm") = 8.0, py::arg("threads") = -1);
    m.def("batch_formal_check", &batch_formal_check, "Batch narrow-band SDF checks",
          py::arg("v_tgt"), py::arg("f_tgt"), py::arg("V_cands"), py::arg("F_cands"),
          py::arg("clearance"), py::arg("voxel") = 0.30, py::arg("band_mm") = 8.0, py::arg("threads") = -1);

    // 诊断/可视化辅助
    m.def("min_clearance_point", &min_clearance_point, "Find thinnest point on target vs candidate",
          py::arg("v_tgt"), py::arg("f_tgt"), py::arg("v_cand"), py::arg("f_cand"));
    m.def("mesh_section", &mesh_section, "Triangle-plane intersection segments",
          py::arg("v"), py::arg("f"), py::arg("p0"), py::arg("nrm"));
    m.def("thin_regions", &thin_regions, "Cluster thin-wall vertices into regions",
          py::arg("v_tgt"), py::arg("f_tgt"), py::arg("v_cand"), py::arg("f_cand"),
          py::arg("thr_mm"), py::arg("radius_mm"));
    m.def("label_regions", &label_regions, "Label regions with shoe semantics",
          py::arg("v_tgt"), py::arg("regions"));
}