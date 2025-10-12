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
#include <fstream>
#include <array>
#include <iomanip>

// OpenNURBS includes
#include "opennurbs.h"

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
                              double radius, double voxel, int max_iterations=15000, int confidence=500) {
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
    
    // 更严格的 RANSAC 参数以提高稳定性
    auto result = pipelines::registration::RegistrationRANSACBasedOnFeatureMatching(
        src, tgt, *fsrc, *ftgt, true, thr,
        pipelines::registration::TransformationEstimationPointToPoint(false), 4,
        checkers,
        pipelines::registration::RANSACConvergenceCriteria(max_iterations, confidence));
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

// 更稳健的多起点对齐函数
py::dict align_icp_robust(py::array_t<double> v_src, py::array_t<int> f_src,
                          py::array_t<double> v_tgt, py::array_t<int> f_tgt,
                          double voxel, double fpfh_radius, double icp_thr, 
                          int n_starts=5, int max_iterations=20000, int confidence=800) {
    auto mS = mesh_from_np(v_src, f_src);
    auto mT = mesh_from_np(v_tgt, f_tgt);
    
    Eigen::Matrix4d Tbest = Eigen::Matrix4d::Identity();
    double best_score = std::numeric_limits<double>::infinity();
    bool best_mirrored = false;
    
    // 尝试不同的参数组合
    std::vector<std::pair<double, double>> param_pairs = {
        {voxel, fpfh_radius},
        {voxel * 0.8, fpfh_radius * 0.8},
        {voxel * 1.2, fpfh_radius * 1.2},
        {voxel * 0.6, fpfh_radius * 0.6},
        {voxel * 1.5, fpfh_radius * 1.5}
    };
    
    for (int attempt = 0; attempt < std::min(n_starts, (int)param_pairs.size()); ++attempt) {
        auto [v, r] = param_pairs[attempt];
        auto pT = sample_pcd(*mT, 50000)->VoxelDownSample(v);
        
        // 原始方向
        auto pS0 = sample_pcd(*mS, 50000)->VoxelDownSample(v);
        Eigen::Matrix4d T0 = icp(*pS0, *pT, ransac(*pS0, *pT, r, v, max_iterations, confidence), icp_thr);
        auto Sa = *mS; Sa.Transform(T0);
        double ch0 = chamfer(*sample_pcd(Sa, 20000), *sample_pcd(*mT, 20000));
        
        // 镜像方向
        Eigen::Matrix4d M = Eigen::Matrix4d::Identity(); M(0, 0) = -1.0;
        auto Sm = *mS; Sm.Transform(M);
        auto pSm = sample_pcd(Sm, 50000)->VoxelDownSample(v);
        Eigen::Matrix4d Tm = icp(*pSm, *pT, ransac(*pSm, *pT, r, v, max_iterations, confidence), icp_thr);
        auto Sb = Sm; Sb.Transform(Tm);
        double chm = chamfer(*sample_pcd(Sb, 20000), *sample_pcd(*mT, 20000));
        
        // 选择更好的结果
        if (chm < ch0 && chm < best_score) {
            Tbest = Tm * M;
            best_score = chm;
            best_mirrored = true;
        } else if (ch0 < best_score) {
            Tbest = T0;
            best_score = ch0;
            best_mirrored = false;
        }
    }
    
    py::array_t<double> Tnp({4, 4});
    auto r = Tnp.mutable_unchecked<2>();
    for (int i = 0; i < 4; ++i) for (int j = 0; j < 4; ++j) r(i, j) = Tbest(i, j);
    
    return py::dict("T"_a = Tnp, "chamfer"_a = best_score, "mirrored"_a = best_mirrored);
}

// 高精度对齐函数 - 通过提高采样量和迭代数来提升准确率
py::dict align_icp_high_accuracy(py::array_t<double> v_src, py::array_t<int> f_src,
                                 py::array_t<double> v_tgt, py::array_t<int> f_tgt,
                                 double voxel, double fpfh_radius, double icp_thr,
                                 int initial_samples=100000, int chamfer_samples=50000,
                                 int max_iterations=50000, int confidence=1500, int n_starts=7) {
    auto mS = mesh_from_np(v_src, f_src);
    auto mT = mesh_from_np(v_tgt, f_tgt);
    
    Eigen::Matrix4d Tbest = Eigen::Matrix4d::Identity();
    double best_score = std::numeric_limits<double>::infinity();
    bool best_mirrored = false;
    
    // 更精细的参数组合，专注于高精度
    std::vector<std::pair<double, double>> param_pairs = {
        {voxel, fpfh_radius},                    // 标准参数
        {voxel * 0.7, fpfh_radius * 0.7},       // 更精细
        {voxel * 0.5, fpfh_radius * 0.5},       // 超精细
        {voxel * 1.3, fpfh_radius * 1.3},       // 稍粗糙
        {voxel * 0.9, fpfh_radius * 0.9},       // 微调
        {voxel * 1.1, fpfh_radius * 1.1},       // 微调
        {voxel * 0.3, fpfh_radius * 0.3}        // 极高精度
    };
    
    for (int attempt = 0; attempt < std::min(n_starts, (int)param_pairs.size()); ++attempt) {
        auto [v, r] = param_pairs[attempt];
        
        // 使用更高的采样量
        auto pT = sample_pcd(*mT, initial_samples)->VoxelDownSample(v);
        
        // 原始方向
        auto pS0 = sample_pcd(*mS, initial_samples)->VoxelDownSample(v);
        Eigen::Matrix4d T0 = icp(*pS0, *pT, ransac(*pS0, *pT, r, v, max_iterations, confidence), icp_thr);
        auto Sa = *mS; Sa.Transform(T0);
        double ch0 = chamfer(*sample_pcd(Sa, chamfer_samples), *sample_pcd(*mT, chamfer_samples));
        
        // 镜像方向
        Eigen::Matrix4d M = Eigen::Matrix4d::Identity(); M(0, 0) = -1.0;
        auto Sm = *mS; Sm.Transform(M);
        auto pSm = sample_pcd(Sm, initial_samples)->VoxelDownSample(v);
        Eigen::Matrix4d Tm = icp(*pSm, *pT, ransac(*pSm, *pT, r, v, max_iterations, confidence), icp_thr);
        auto Sb = Sm; Sb.Transform(Tm);
        double chm = chamfer(*sample_pcd(Sb, chamfer_samples), *sample_pcd(*mT, chamfer_samples));
        
        // 选择更好的结果
        if (chm < ch0 && chm < best_score) {
            Tbest = Tm * M;
            best_score = chm;
            best_mirrored = true;
        } else if (ch0 < best_score) {
            Tbest = T0;
            best_score = ch0;
            best_mirrored = false;
        }
    }
    
    py::array_t<double> Tnp({4, 4});
    auto r = Tnp.mutable_unchecked<2>();
    for (int i = 0; i < 4; ++i) for (int j = 0; j < 4; ++j) r(i, j) = Tbest(i, j);
    
    return py::dict("T"_a = Tnp, "chamfer"_a = best_score, "mirrored"_a = best_mirrored);
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

    double min_c = 0, mean_c = 0, p01 = 0, p05 = 0, p10 = 0, p15 = 0, p20 = 0, p50 = 0; 
    bool pass = false;
    if (!inner.empty()) {
        std::sort(inner.begin(), inner.end());
        min_c = inner.front();  // Minimum clearance (smallest distance from target to candidate interior)
        mean_c = std::accumulate(inner.begin(), inner.end(), 0.0) / inner.size();
        
        // 计算真实的百分位数
        size_t n = inner.size();
        auto percentile = [&](double p) -> double {
            size_t k = (size_t)std::floor(p * n);
            if (k >= n) k = n - 1;
            return inner[k];
        };
        
        p01 = percentile(0.01);
        p05 = percentile(0.05);
        p10 = percentile(0.10);
        p15 = percentile(0.15);
        p20 = percentile(0.20);
        p50 = percentile(0.50);
        
        // Pass only if ALL points are inside (inside_ratio == 1.0) AND minimum clearance is sufficient
        pass = (inside_ratio >= 0.999) && (min_c >= clearance);  // Allow 0.1% tolerance for numerical errors
    }
    return py::dict("pass"_a = pass, "min_clearance"_a = min_c, "mean_clearance"_a = mean_c,
                    "p01_clearance"_a = p01, "p05_clearance"_a = p05, "p10_clearance"_a = p10,
                    "p15_clearance"_a = p15, "p20_clearance"_a = p20, "p50_clearance"_a = p50,
                    "inside_ratio"_a = inside_ratio);
}

// 基于顶点的间隙检查 - 不使用采样，直接使用所有顶点
py::dict clearance_vertex_based(py::array_t<double> v_tgt, py::array_t<int> f_tgt,
                               py::array_t<double> v_cand, py::array_t<int> f_cand,
                               double clearance, double safety_delta) {
    auto mT = mesh_from_np(v_tgt, f_tgt);
    auto mC = mesh_from_np(v_cand, f_cand);
    
    // 直接使用目标网格的所有顶点，不进行采样
    auto pts = std::make_shared<geometry::PointCloud>();
    pts->points_ = mT->vertices_;

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

    double min_c = 0, mean_c = 0, p01 = 0, p05 = 0, p10 = 0, p15 = 0, p20 = 0, p50 = 0; 
    bool pass = false;
    if (!inner.empty()) {
        std::sort(inner.begin(), inner.end());
        min_c = inner.front();  // Minimum clearance (smallest distance from target to candidate interior)
        mean_c = std::accumulate(inner.begin(), inner.end(), 0.0) / inner.size();
        
        // 计算真实的百分位数
        size_t n = inner.size();
        auto percentile = [&](double p) -> double {
            size_t k = (size_t)std::floor(p * n);
            if (k >= n) k = n - 1;
            return inner[k];
        };
        
        p01 = percentile(0.01);
        p05 = percentile(0.05);
        p10 = percentile(0.10);
        p15 = percentile(0.15);
        p20 = percentile(0.20);
        p50 = percentile(0.50);
        
        // Pass only if ALL vertices are inside (inside_ratio == 1.0) AND minimum clearance is sufficient
        pass = (inside_ratio >= 0.999) && (min_c >= clearance);  // Allow 0.1% tolerance for numerical errors
    }
    return py::dict("pass"_a = pass, "min_clearance"_a = min_c, "mean_clearance"_a = mean_c,
                    "p01_clearance"_a = p01, "p05_clearance"_a = p05, "p10_clearance"_a = p10,
                    "p15_clearance"_a = p15, "p20_clearance"_a = p20, "p50_clearance"_a = p50,
                    "inside_ratio"_a = inside_ratio);
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

// ----------------------------- STL to 3DM 转换 -----------------------------

py::dict stl_to_3dm(const std::string& stl_path, const std::string& output_3dm_path) {
    try {
        ON::Begin();
        
        // 1. 读取 STL 文件
        std::ifstream stl(stl_path, std::ios::binary);
        if (!stl) {
            ON::End();
            return py::dict("success"_a = false, "error"_a = "Cannot open STL file");
        }

        // STL 二进制前 80 字节是 header
        stl.seekg(80);
        uint32_t numTriangles;
        stl.read(reinterpret_cast<char*>(&numTriangles), 4);

        if (numTriangles == 0) {
            ON::End();
            stl.close();
            return py::dict("success"_a = false, "error"_a = "No triangles found in STL file");
        }

        std::vector<ON_3fPoint> vertices;
        std::vector<std::array<int, 3>> faces;
        vertices.reserve(numTriangles * 3);
        faces.reserve(numTriangles);

        for (uint32_t i = 0; i < numTriangles; ++i) {
            float normal[3];
            float v[9];
            uint16_t attr;

            stl.read(reinterpret_cast<char*>(normal), 12);
            stl.read(reinterpret_cast<char*>(v), 36);
            stl.read(reinterpret_cast<char*>(&attr), 2);

            int baseIdx = vertices.size();
            vertices.push_back(ON_3fPoint(v[0], v[1], v[2]));
            vertices.push_back(ON_3fPoint(v[3], v[4], v[5]));
            vertices.push_back(ON_3fPoint(v[6], v[7], v[8]));

            faces.push_back({baseIdx, baseIdx + 1, baseIdx + 2});
        }
        stl.close();

        // 2. 创建 ON_Mesh
        ON_Mesh mesh;
        for (const auto &v : vertices) {
            mesh.m_V.Append(v);
        }

        for (const auto &f : faces) {
            ON_MeshFace& face = mesh.m_F.AppendNew();
            face.vi[0] = f[0];
            face.vi[1] = f[1];
            face.vi[2] = f[2];
            face.vi[3] = f[2];  // 三角形面，第4个顶点重复
        }

        mesh.ComputeVertexNormals();

        // 3. 保存到 3DM - 使用直接的方法
        ONX_Model model;
        ON_ModelComponentReference mesh_ref = model.AddModelGeometryComponent(&mesh, nullptr);
        
        bool write_success = model.Write(output_3dm_path.c_str(), 70, nullptr);
        
        ON::End();
        
        if (!write_success) {
            return py::dict("success"_a = false, "error"_a = "Failed to write 3DM file");
        }
        
        return py::dict("success"_a = true, "message"_a = "STL successfully converted to 3DM",
                        "triangle_count"_a = (int)numTriangles, "vertex_count"_a = (int)vertices.size());
        
    } catch (const std::exception &e) {
        ON::End();
        return py::dict("success"_a = false, "error"_a = e.what());
    }
}

// ----------------------------- 中线对齐 + Adam优化 -----------------------------

// PCA结果结构体
struct PCAResult {
    Eigen::Vector3d center;
    Eigen::Vector3d main_axis;
    Eigen::Vector3d side_axis;
    double length;
};

// 计算网格的PCA主轴
static PCAResult compute_pca_axis(const geometry::TriangleMesh& mesh) {
    PCAResult result;
    
    // 1. 计算中心点
    Eigen::Vector3d center = Eigen::Vector3d::Zero();
    for (const auto& v : mesh.vertices_) {
        center += v;
    }
    center /= std::max<size_t>(1, mesh.vertices_.size());
    result.center = center;
    
    // 2. 构建协方差矩阵
    Eigen::Matrix3d cov = Eigen::Matrix3d::Zero();
    for (const auto& v : mesh.vertices_) {
        Eigen::Vector3d d = v - center;
        cov += d * d.transpose();
    }
    cov /= std::max<size_t>(1, mesh.vertices_.size());
    
    // 3. 特征值分解
    Eigen::SelfAdjointEigenSolver<Eigen::Matrix3d> solver(cov);
    
    // 特征向量按特征值升序排列
    result.main_axis = solver.eigenvectors().col(2);  // 最大特征向量（主轴）
    result.side_axis = solver.eigenvectors().col(1);  // 次大特征向量（侧轴）
    
    // 4. 计算长度
    double min_proj = std::numeric_limits<double>::max();
    double max_proj = std::numeric_limits<double>::lowest();
    for (const auto& v : mesh.vertices_) {
        double proj = (v - center).dot(result.main_axis);
        min_proj = std::min(min_proj, proj);
        max_proj = std::max(max_proj, proj);
    }
    result.length = max_proj - min_proj;
    
    return result;
}

// 构建中线对齐的变换矩阵
static Eigen::Matrix4d build_centerline_transform(
    const PCAResult& src_pca,
    const PCAResult& tgt_pca,
    bool mirror,
    bool flip
) {
    Eigen::Matrix4d T = Eigen::Matrix4d::Identity();
    
    // 1. 处理源轴方向
    Eigen::Vector3d src_axis = src_pca.main_axis;
    Eigen::Vector3d src_center = src_pca.center;
    
    if (flip) {
        src_axis = -src_axis;
    }
    if (mirror) {
        src_axis.x() = -src_axis.x();
        src_center.x() = -src_center.x();
    }
    
    // 2. 构建旋转矩阵（对齐主轴）
    Eigen::Vector3d tgt_axis = tgt_pca.main_axis;
    Eigen::Quaterniond q;
    q.setFromTwoVectors(src_axis, tgt_axis);
    T.block<3,3>(0,0) = q.toRotationMatrix();
    
    // 3. 平移（对齐中心）
    Eigen::Vector3d rotated_center = T.block<3,3>(0,0) * src_center;
    T.block<3,1>(0,3) = tgt_pca.center - rotated_center;
    
    return T;
}

// 应用参数化调整（平移+旋转）
static Eigen::Matrix4d apply_parametric_adjustment(
    const Eigen::Matrix4d& T_base,
    const PCAResult& tgt_pca,
    double translate_mm,
    double rotate_deg
) {
    Eigen::Matrix4d T = T_base;
    
    // 1. 沿中线平移
    T.block<3,1>(0,3) += tgt_pca.main_axis * translate_mm;
    
    // 2. 绕中线旋转
    if (std::abs(rotate_deg) > 1e-6) {
        double angle_rad = rotate_deg * M_PI / 180.0;
        Eigen::AngleAxisd rotation(angle_rad, tgt_pca.main_axis);
        Eigen::Matrix3d R = rotation.toRotationMatrix();
        
        Eigen::Vector3d offset = T.block<3,1>(0,3) - tgt_pca.center;
        T.block<3,3>(0,0) = R * T.block<3,3>(0,0);
        T.block<3,1>(0,3) = tgt_pca.center + R * offset;
    }
    
    return T;
}

// 评价对齐质量（优化版本 - 复用采样点和场景）
static double evaluate_alignment_score_optimized(
    const std::vector<Eigen::Vector3d>& sample_points,  // 预采样的点（复用）
    t::geometry::RaycastingScene& scene,                 // 预构建的场景（复用，非const）
    const Eigen::Matrix4d& transform                     // 变换矩阵
) {
    // 应用变换到采样点
    std::vector<float> buf;
    buf.reserve(sample_points.size() * 3);
    for (const auto& p : sample_points) {
        Eigen::Vector4d ph(p.x(), p.y(), p.z(), 1.0);
        Eigen::Vector3d pt = (transform * ph).head<3>();
        buf.push_back((float)pt.x());
        buf.push_back((float)pt.y());
        buf.push_back((float)pt.z());
    }
    core::Tensor q(buf, {(int64_t)sample_points.size(), 3}, core::Float32);
    
    auto sdist = scene.ComputeSignedDistance(q);
    auto inside = scene.ComputeOccupancy(q);
    
    const float* sdv = sdist.GetDataPtr<float>();
    const float* inv = inside.GetDataPtr<float>();
    size_t n = sample_points.size();
    
    // 快速统计（避免创建临时vector）
    double sum_clearance = 0.0;
    size_t inside_cnt = 0;
    
    for (size_t i = 0; i < n; ++i) {
        if (inv[i] > 0.5f) {
            inside_cnt++;
            sum_clearance += std::abs((double)sdv[i]);
        }
    }
    
    if (inside_cnt == 0) return -1000.0;
    
    double inside_ratio = (double)inside_cnt / n;
    double mean_clearance = sum_clearance / inside_cnt;
    
    // 综合得分
    if (inside_ratio >= 0.99) {
        return inside_ratio * 100.0 + mean_clearance * 10.0;
    } else {
        return inside_ratio * 50.0;
    }
}

// 评价对齐质量（快速版本，用于优化）
static double evaluate_alignment_score(
    geometry::TriangleMesh target,
    geometry::TriangleMesh candidate_aligned,
    size_t samples = 30000
) {
    // 构建RaycastingScene
    t::geometry::TriangleMesh tmC = t::geometry::TriangleMesh::FromLegacy(candidate_aligned);
    t::geometry::RaycastingScene scene;
    scene.AddTriangles(tmC);
    
    // 采样目标表面
    auto pts = target.SamplePointsUniformly(samples);
    std::vector<float> buf;
    buf.reserve(pts->points_.size() * 3);
    for (const auto& p : pts->points_) {
        buf.push_back((float)p.x());
        buf.push_back((float)p.y());
        buf.push_back((float)p.z());
    }
    core::Tensor q(buf, {(int64_t)pts->points_.size(), 3}, core::Float32);
    
    auto sdist = scene.ComputeSignedDistance(q);
    auto inside = scene.ComputeOccupancy(q);
    
    std::vector<float> sdv(sdist.GetDataPtr<float>(), sdist.GetDataPtr<float>() + sdist.NumElements());
    std::vector<float> inv(inside.GetDataPtr<float>(), inside.GetDataPtr<float>() + inside.NumElements());
    
    // 统计
    std::vector<double> clearances;
    size_t inside_cnt = 0;
    for (size_t i = 0; i < sdv.size(); ++i) {
        if (inv[i] > 0.5f) {
            inside_cnt++;
            clearances.push_back(std::abs((double)sdv[i]));
        }
    }
    
    double inside_ratio = (double)inside_cnt / std::max<size_t>(1, sdv.size());
    
    if (clearances.empty()) {
        return -1000.0;
    }
    
    double mean_clearance = std::accumulate(clearances.begin(), clearances.end(), 0.0) / clearances.size();
    
    // 综合得分：覆盖率优先，平均间隙次之
    double score;
    if (inside_ratio >= 0.99) {
        score = inside_ratio * 100.0 + mean_clearance * 10.0;
    } else {
        score = inside_ratio * 50.0;
    }
    
    return score;
}

// Adam优化器类
class AdamOptimizer {
public:
    AdamOptimizer(double learning_rate = 0.5,
                  double beta1 = 0.9,
                  double beta2 = 0.999,
                  double epsilon = 1e-8)
        : lr_(learning_rate), beta1_(beta1), beta2_(beta2), epsilon_(epsilon), t_(0) {}
    
    // 执行一步优化
    Eigen::Vector2d step(const Eigen::Vector2d& gradient) {
        t_++;
        
        // 更新一阶矩估计（动量）
        m_ = beta1_ * m_ + (1.0 - beta1_) * gradient;
        
        // 更新二阶矩估计（自适应学习率）
        v_ = beta2_ * v_ + (1.0 - beta2_) * gradient.cwiseProduct(gradient);
        
        // 偏差修正
        Eigen::Vector2d m_hat = m_ / (1.0 - std::pow(beta1_, t_));
        Eigen::Vector2d v_hat = v_ / (1.0 - std::pow(beta2_, t_));
        
        // 计算更新步长
        Eigen::Vector2d update = Eigen::Vector2d::Zero();
        for (int i = 0; i < 2; ++i) {
            update(i) = -lr_ * m_hat(i) / (std::sqrt(v_hat(i)) + epsilon_);
        }
        
        return update;
    }
    
    void reset() {
        m_.setZero();
        v_.setZero();
        t_ = 0;
    }
    
private:
    double lr_;
    double beta1_;
    double beta2_;
    double epsilon_;
    int t_;
    Eigen::Vector2d m_{0, 0};  // 一阶矩
    Eigen::Vector2d v_{0, 0};  // 二阶矩
};

// 数值梯度计算（优化版本 - 复用场景和采样点）
static Eigen::Vector2d compute_numerical_gradient_optimized(
    const std::vector<Eigen::Vector3d>& sample_points,
    t::geometry::RaycastingScene& scene,  // 非const（RaycastingScene方法非const）
    const Eigen::Matrix4d& T_base,
    const PCAResult& tgt_pca,
    const Eigen::Vector2d& params,
    double epsilon = 0.5
) {
    Eigen::Vector2d gradient;
    
    for (int i = 0; i < 2; ++i) {
        // 正向扰动
        Eigen::Vector2d params_plus = params;
        params_plus(i) += epsilon;
        Eigen::Matrix4d T_plus = apply_parametric_adjustment(T_base, tgt_pca, params_plus(0), params_plus(1));
        double score_plus = evaluate_alignment_score_optimized(sample_points, scene, T_plus);
        
        // 负向扰动
        Eigen::Vector2d params_minus = params;
        params_minus(i) -= epsilon;
        Eigen::Matrix4d T_minus = apply_parametric_adjustment(T_base, tgt_pca, params_minus(0), params_minus(1));
        double score_minus = evaluate_alignment_score_optimized(sample_points, scene, T_minus);
        
        // 中心差分
        gradient(i) = (score_plus - score_minus) / (2.0 * epsilon);
    }
    
    return gradient;
}

// 主函数：基于中线的Adam优化对齐（高性能版本）
py::dict align_centerline_adam(
    py::array_t<double> v_src, py::array_t<int> f_src,
    py::array_t<double> v_tgt, py::array_t<int> f_tgt,
    double voxel = 5.0,
    double fpfh_radius = 10.0,
    double icp_thr = 15.0,
    int max_iterations = 50,
    double learning_rate = 0.5,
    double convergence_tol = 0.1,
    bool verbose = false
) {
    auto mS = mesh_from_np(v_src, f_src);
    auto mT = mesh_from_np(v_tgt, f_tgt);
    
    if (verbose) std::cout << "\n=== Centerline Adam Alignment (Optimized) ===" << std::endl;
    
    // ========== 性能优化1: 预处理 - 采样和场景构建（只做一次）==========
    // 采样目标表面点（复用）
    const size_t quick_samples = 5000;   // 快速评估用少量采样
    const size_t final_samples = 15000;  // 最终评估用较多采样
    
    auto pts_quick = mT->SamplePointsUniformly(quick_samples);
    std::vector<Eigen::Vector3d> sample_points_quick;
    sample_points_quick.reserve(pts_quick->points_.size());
    for (const auto& p : pts_quick->points_) {
        sample_points_quick.push_back(p);
    }
    
    // 构建目标的RaycastingScene（注意：是用源网格构建场景，目标点去查询）
    // 修正：应该用候选（对齐后的源）构建场景
    
    if (verbose) std::cout << "[Optimization] Pre-sampled " << quick_samples << " points for fast evaluation" << std::endl;
    
    // 阶段1: 计算PCA中线
    if (verbose) std::cout << "\n[Stage 1] Computing PCA centerlines..." << std::endl;
    PCAResult src_pca = compute_pca_axis(*mS);
    PCAResult tgt_pca = compute_pca_axis(*mT);
    
    if (verbose) {
        std::cout << "  Source: center=(" << src_pca.center.transpose() 
                  << "), axis=(" << src_pca.main_axis.transpose() << ")" << std::endl;
        std::cout << "  Target: center=(" << tgt_pca.center.transpose() 
                  << "), axis=(" << tgt_pca.main_axis.transpose() << ")" << std::endl;
    }
    
    // ========== 性能优化2: 粗网格快速筛选最佳方向 ==========
    if (verbose) std::cout << "\n[Stage 2] Quick direction screening (coarse grid)..." << std::endl;
    
    struct DirectionResult {
        Eigen::Matrix4d T;
        double score;
        bool mirror;
        bool flip;
        Eigen::Vector2d params;
    };
    
    std::vector<std::pair<bool, bool>> directions = {
        {false, false}, {true, false}, {false, true}, {true, true}
    };
    
    // ========== 优化3: 粗网格快速筛选（5x5=25次评估，找最佳方向）==========
    std::vector<double> direction_scores(4, -std::numeric_limits<double>::infinity());
    
    for (size_t dir_idx = 0; dir_idx < 4; ++dir_idx) {
        bool mirror = directions[dir_idx].first;
        bool flip = directions[dir_idx].second;
        
        Eigen::Matrix4d T_base = build_centerline_transform(src_pca, tgt_pca, mirror, flip);
        
        // 粗网格：只测试5个关键点
        std::vector<double> grid_t = {-10, -5, 0, 5, 10};  // 5个平移
        std::vector<double> grid_r = {-5, -2, 0, 2, 5};    // 5个旋转
        
        auto mS_transformed = *mS;
        mS_transformed.Transform(T_base);
        
        // 构建场景（每个方向构建一次）
        t::geometry::TriangleMesh tmS = t::geometry::TriangleMesh::FromLegacy(mS_transformed);
        t::geometry::RaycastingScene scene;
        scene.AddTriangles(tmS);
        
        for (double t : grid_t) {
            for (double r : grid_r) {
                Eigen::Matrix4d T_adj = apply_parametric_adjustment(Eigen::Matrix4d::Identity(), tgt_pca, t, r);
                double score = evaluate_alignment_score_optimized(sample_points_quick, scene, T_adj);
                direction_scores[dir_idx] = std::max(direction_scores[dir_idx], score);
            }
        }
        
        if (verbose) {
            std::cout << "  Dir " << (dir_idx+1) << " (";
            if (mirror) std::cout << "M";
            if (flip) std::cout << "F";
            if (!mirror && !flip) std::cout << "O";
            std::cout << "): score=" << direction_scores[dir_idx] << std::endl;
        }
    }
    
    // 选择最佳方向（只优化这一个）
    size_t best_dir_idx = std::distance(direction_scores.begin(), 
        std::max_element(direction_scores.begin(), direction_scores.end()));
    
    bool mirror = directions[best_dir_idx].first;
    bool flip = directions[best_dir_idx].second;
    
    if (verbose) {
        std::cout << "\n[Stage 3] Optimizing best direction: ";
        if (mirror) std::cout << "Mirror ";
        if (flip) std::cout << "Flip ";
        if (!mirror && !flip) std::cout << "Original";
        std::cout << " (score=" << direction_scores[best_dir_idx] << ")" << std::endl;
    }
    
    // ========== 优化4: 只对最佳方向进行Adam优化 ==========
    Eigen::Matrix4d T_base = build_centerline_transform(src_pca, tgt_pca, mirror, flip);
    auto mS_base = *mS;
    mS_base.Transform(T_base);
    
    // 构建场景（只构建一次）
    t::geometry::TriangleMesh tmS = t::geometry::TriangleMesh::FromLegacy(mS_base);
    t::geometry::RaycastingScene scene;
    scene.AddTriangles(tmS);
    
    if (verbose) std::cout << "  [Adam] Starting with " << max_iterations << " max iterations..." << std::endl;
    
    AdamOptimizer optimizer(learning_rate, 0.9, 0.999, 1e-8);
    Eigen::Vector2d params(0.0, 0.0);
    double best_score = -std::numeric_limits<double>::infinity();
    Eigen::Vector2d best_params = params;
    int no_improve_count = 0;
    
    for (int iter = 0; iter < max_iterations; ++iter) {
        // 计算当前得分（使用优化版本）
        Eigen::Matrix4d T_current = apply_parametric_adjustment(Eigen::Matrix4d::Identity(), tgt_pca, params(0), params(1));
        double current_score = evaluate_alignment_score_optimized(sample_points_quick, scene, T_current);
        
        if (current_score > best_score) {
            best_score = current_score;
            best_params = params;
            no_improve_count = 0;
            if (verbose && iter % 5 == 0) {
                std::cout << "    Iter " << std::setw(2) << iter << ": score=" << current_score << " ✓" << std::endl;
            }
        } else {
            no_improve_count++;
        }
        
        // 早停：连续5次无改善（优化：从10降到5）
        if (no_improve_count >= 5) {
            if (verbose) std::cout << "    Early stop at iter " << iter << std::endl;
            break;
        }
        
        // 计算梯度（使用优化版本）
        Eigen::Vector2d gradient = compute_numerical_gradient_optimized(sample_points_quick, scene, 
            Eigen::Matrix4d::Identity(), tgt_pca, params, 0.5);
        
        Eigen::Vector2d update = optimizer.step(gradient);
        params += update;
        
        // 边界约束
        params(0) = std::max(-20.0, std::min(20.0, params(0)));
        params(1) = std::max(-10.0, std::min(10.0, params(1)));
        
        if (update.norm() < convergence_tol) {
            if (verbose) std::cout << "    Converged at iter " << iter << std::endl;
            break;
        }
    }
    
    if (verbose) {
        std::cout << "  Best: t=" << best_params(0) << "mm, r=" << best_params(1) << "°, score=" << best_score << std::endl;
    }
    
    // 构建最佳变换
    Eigen::Matrix4d T_opt = apply_parametric_adjustment(Eigen::Matrix4d::Identity(), tgt_pca, best_params(0), best_params(1));
    Eigen::Matrix4d T_best = T_opt * T_base;
    
    // ========== 优化5: 跳过ICP微调（Adam已经够准确）==========
    // 直接使用Adam优化的结果，节省3-5秒
    Eigen::Matrix4d T_final = T_best;
    auto mS_final = *mS;
    mS_final.Transform(T_final);
    
    // 最终评价（使用中等采样量）
    double final_score = evaluate_alignment_score(mS_final, *mT, 15000);
    
    // 计算Chamfer距离（减少采样）
    double ch = chamfer(*sample_pcd(mS_final, 10000), *sample_pcd(*mT, 10000));
    
    // ========== 优化6: 轻量级间隙计算（复用之前的采样）==========
    t::geometry::TriangleMesh tmC_final = t::geometry::TriangleMesh::FromLegacy(mS_final);
    t::geometry::RaycastingScene scene_final;
    scene_final.AddTriangles(tmC_final);
    
    // 使用15000采样点计算详细指标
    auto pts_final = mT->SamplePointsUniformly(15000);
    std::vector<float> buf_final;
    buf_final.reserve(pts_final->points_.size() * 3);
    for (const auto& p : pts_final->points_) {
        buf_final.push_back((float)p.x());
        buf_final.push_back((float)p.y());
        buf_final.push_back((float)p.z());
    }
    core::Tensor q_final(buf_final, {(int64_t)pts_final->points_.size(), 3}, core::Float32);
    
    auto sdist_final = scene_final.ComputeSignedDistance(q_final);
    auto inside_final = scene_final.ComputeOccupancy(q_final);
    
    const float* sdv_final = sdist_final.GetDataPtr<float>();
    const float* inv_final = inside_final.GetDataPtr<float>();
    size_t n_final = pts_final->points_.size();
    
    std::vector<double> clearances_final;
    clearances_final.reserve(n_final);
    size_t inside_cnt_final = 0;
    
    for (size_t i = 0; i < n_final; ++i) {
        if (inv_final[i] > 0.5f) {
            inside_cnt_final++;
            clearances_final.push_back(std::abs((double)sdv_final[i]));
        }
    }
    
    double inside_ratio_final = (double)inside_cnt_final / n_final;
    double min_clear = 0, mean_clear = 0, p15_clear = 0;
    
    if (!clearances_final.empty()) {
        std::sort(clearances_final.begin(), clearances_final.end());
        min_clear = clearances_final.front();
        mean_clear = std::accumulate(clearances_final.begin(), clearances_final.end(), 0.0) / clearances_final.size();
        size_t k15 = (size_t)std::floor(0.15 * clearances_final.size());
        if (k15 >= clearances_final.size()) k15 = clearances_final.size() - 1;
        p15_clear = clearances_final[k15];
    }
    
    if (verbose) {
        std::cout << "\n=== Final Result ===" << std::endl;
        std::cout << "  Method: Centerline + Adam (Optimized)" << std::endl;
        std::cout << "  Mirrored: " << (mirror ? "Yes" : "No") << std::endl;
        std::cout << "  Flipped: " << (flip ? "Yes" : "No") << std::endl;
        std::cout << "  Translation: " << best_params(0) << " mm" << std::endl;
        std::cout << "  Rotation: " << best_params(1) << " °" << std::endl;
        std::cout << "  Chamfer: " << ch << " mm" << std::endl;
        std::cout << "  Coverage: " << (inside_ratio_final * 100) << "%" << std::endl;
        std::cout << "  Mean clearance: " << mean_clear << " mm" << std::endl;
    }
    
    // 转换变换矩阵为NumPy数组
    py::array_t<double> Tnp({4, 4});
    auto r = Tnp.mutable_unchecked<2>();
    for (int i = 0; i < 4; ++i) {
        for (int j = 0; j < 4; ++j) {
            r(i, j) = T_final(i, j);
        }
    }
    
    // 返回结果（格式与align_icp_with_mirror完全一致）
    py::dict result;
    result["T"] = Tnp;
    result["chamfer"] = ch;
    result["mirrored"] = mirror;  // 使用之前确定的mirror变量
    
    // 额外信息（新增，不影响兼容性）
    result["flipped"] = flip;  // 使用之前确定的flip变量
    result["translate_offset_mm"] = best_params(0);
    result["rotate_offset_deg"] = best_params(1);
    result["optimization_score"] = final_score;
    result["inside_ratio"] = inside_ratio_final;
    result["mean_clearance"] = mean_clear;
    result["min_clearance"] = min_clear;
    result["p15_clearance"] = p15_clear;
    
    return result;
}

// ----------------------------- PYBIND11 模块 -----------------------------

PYBIND11_MODULE(cppcore, m) {
    m.doc() = "C++17 core for Shoe Last Matcher (v0.5)";

    // STL 转 3DM
    m.def("stl_to_3dm", &stl_to_3dm, "Convert STL file to 3DM format",
          py::arg("stl_path"), py::arg("output_3dm_path"));

    // 粗特征
    m.def("coarse_features", &coarse_features, "Compute coarse descriptors");

    // 对齐
    m.def("align_icp", &align_icp, "Rigid registration (RANSAC→ICP) with chamfer",
          py::arg("v_src"), py::arg("f_src"), py::arg("v_tgt"), py::arg("f_tgt"),
          py::arg("voxel"), py::arg("fpfh_radius"), py::arg("icp_thr"));
    m.def("align_icp_with_mirror", &align_icp_with_mirror, "Registration with YZ-mirror option",
          py::arg("v_src"), py::arg("f_src"), py::arg("v_tgt"), py::arg("f_tgt"),
          py::arg("voxel"), py::arg("fpfh_radius"), py::arg("icp_thr"));
    m.def("align_icp_robust", &align_icp_robust, "Robust multi-start registration with improved RANSAC",
          py::arg("v_src"), py::arg("f_src"), py::arg("v_tgt"), py::arg("f_tgt"),
          py::arg("voxel"), py::arg("fpfh_radius"), py::arg("icp_thr"),
          py::arg("n_starts") = 5, py::arg("max_iterations") = 20000, py::arg("confidence") = 800);
    m.def("align_icp_high_accuracy", &align_icp_high_accuracy, "High-accuracy alignment with increased sampling and iterations",
          py::arg("v_src"), py::arg("f_src"), py::arg("v_tgt"), py::arg("f_tgt"),
          py::arg("voxel"), py::arg("fpfh_radius"), py::arg("icp_thr"),
          py::arg("initial_samples") = 100000, py::arg("chamfer_samples") = 50000,
          py::arg("max_iterations") = 50000, py::arg("confidence") = 1500, py::arg("n_starts") = 7);

    // 采样式 SDF + 批量
    m.def("clearance_sampling", &clearance_sampling, "Sampling-based SDF clearance check",
          py::arg("v_tgt"), py::arg("f_tgt"), py::arg("v_cand"), py::arg("f_cand"),
          py::arg("clearance"), py::arg("safety_delta"), py::arg("samples") = 120000);
    m.def("clearance_vertex_based", &clearance_vertex_based, "Vertex-based SDF clearance check (no sampling)",
          py::arg("v_tgt"), py::arg("f_tgt"), py::arg("v_cand"), py::arg("f_cand"),
          py::arg("clearance"), py::arg("safety_delta"));
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
    
    // 中线对齐 + Adam优化 (新增)
    m.def("align_centerline_adam", &align_centerline_adam, 
          "Centerline-based alignment with Adam optimization",
          py::arg("v_src"), py::arg("f_src"),
          py::arg("v_tgt"), py::arg("f_tgt"),
          py::arg("voxel") = 5.0,
          py::arg("fpfh_radius") = 10.0,
          py::arg("icp_thr") = 15.0,
          py::arg("max_iterations") = 50,
          py::arg("learning_rate") = 0.5,
          py::arg("convergence_tol") = 0.1,
          py::arg("verbose") = false);
}