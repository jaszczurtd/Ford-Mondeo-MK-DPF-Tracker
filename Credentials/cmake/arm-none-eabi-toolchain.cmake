set(CMAKE_SYSTEM_NAME Generic)
set(CMAKE_SYSTEM_PROCESSOR arm)
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)

set(CREDENTIALS_TOOLCHAIN_BIN "" CACHE PATH "Directory containing GNU Arm tools")
if(NOT CREDENTIALS_TOOLCHAIN_BIN AND DEFINED ENV{CREDENTIALS_TOOLCHAIN_BIN})
    file(TO_CMAKE_PATH "$ENV{CREDENTIALS_TOOLCHAIN_BIN}" CREDENTIALS_TOOLCHAIN_BIN)
endif()
list(APPEND CMAKE_TRY_COMPILE_PLATFORM_VARIABLES CREDENTIALS_TOOLCHAIN_BIN)

set(_credentials_tool_hints)
if(CREDENTIALS_TOOLCHAIN_BIN)
    list(APPEND _credentials_tool_hints "${CREDENTIALS_TOOLCHAIN_BIN}")
endif()

if(NOT CMAKE_C_COMPILER)
    find_program(CMAKE_C_COMPILER
        NAMES arm-none-eabi-gcc arm-none-eabi-gcc.exe
        HINTS ${_credentials_tool_hints}
        REQUIRED
    )
endif()
if(NOT CMAKE_CXX_COMPILER)
    find_program(CMAKE_CXX_COMPILER
        NAMES arm-none-eabi-g++ arm-none-eabi-g++.exe
        HINTS ${_credentials_tool_hints}
        REQUIRED
    )
endif()
if(NOT CMAKE_AR)
    find_program(CMAKE_AR
        NAMES arm-none-eabi-ar arm-none-eabi-ar.exe
        HINTS ${_credentials_tool_hints}
        REQUIRED
    )
endif()
if(NOT CMAKE_RANLIB)
    find_program(CMAKE_RANLIB
        NAMES arm-none-eabi-ranlib arm-none-eabi-ranlib.exe
        HINTS ${_credentials_tool_hints}
        REQUIRED
    )
endif()
