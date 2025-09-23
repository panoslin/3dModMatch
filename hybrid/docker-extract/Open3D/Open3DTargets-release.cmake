#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "Open3D::tbb" for configuration "Release"
set_property(TARGET Open3D::tbb APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(Open3D::tbb PROPERTIES
  IMPORTED_LOCATION_RELEASE "/usr/lib/x86_64-linux-gnu/libtbb.so.12"
  IMPORTED_SONAME_RELEASE "libtbb.so.12"
  )

list(APPEND _cmake_import_check_targets Open3D::tbb )
list(APPEND _cmake_import_check_files_for_Open3D::tbb "/usr/lib/x86_64-linux-gnu/libtbb.so.12" )

# Import target "Open3D::Open3D" for configuration "Release"
set_property(TARGET Open3D::Open3D APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(Open3D::Open3D PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "Open3D::tbb"
  IMPORTED_LOCATION_RELEASE "/usr/local/lib/libOpen3D.so.0.19.0"
  IMPORTED_SONAME_RELEASE "libOpen3D.so.0.19"
  )

list(APPEND _cmake_import_check_targets Open3D::Open3D )
list(APPEND _cmake_import_check_files_for_Open3D::Open3D "/usr/local/lib/libOpen3D.so.0.19.0" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
