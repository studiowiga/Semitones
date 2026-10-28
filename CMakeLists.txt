cmake_minimum_required(VERSION 3.22)

project(Semitones VERSION 1.3.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(APPLE)
    set(CMAKE_OSX_DEPLOYMENT_TARGET "10.15" CACHE STRING "")
    set(CMAKE_OSX_ARCHITECTURES "arm64;x86_64" CACHE STRING "")
endif()
if(MSVC)
    set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
endif()

# JUCE: local copy (JUCE_DIR) or fetched from GitHub
if(DEFINED JUCE_DIR AND EXISTS "${JUCE_DIR}/CMakeLists.txt")
    add_subdirectory(${JUCE_DIR} JUCE)
else()
    include(FetchContent)
    FetchContent_Declare(JUCE
        GIT_REPOSITORY https://github.com/juce-framework/JUCE.git
        GIT_TAG 8.0.15
        GIT_SHALLOW TRUE)
    FetchContent_MakeAvailable(JUCE)
endif()

juce_add_plugin(Semitones
    COMPANY_NAME "Studio Wiga"
    COMPANY_WEBSITE "https://github.com/studiowiga"
    PLUGIN_MANUFACTURER_CODE Stwg
    PLUGIN_CODE Smtn
    PRODUCT_NAME "Semitones"
    BUNDLE_ID com.studiowiga.semitones
    VERSION ${PROJECT_VERSION}
    FORMATS VST3
    IS_SYNTH FALSE
    NEEDS_MIDI_INPUT TRUE
    NEEDS_MIDI_OUTPUT FALSE
    IS_MIDI_EFFECT FALSE
    EDITOR_WANTS_KEYBOARD_FOCUS FALSE
    COPY_PLUGIN_AFTER_BUILD FALSE
    VST3_CATEGORIES Fx Pitch\ Shift)

juce_generate_juce_header(Semitones)

file(GLOB SEMITONES_ASSETS CONFIGURE_DEPENDS
    ${CMAKE_CURRENT_SOURCE_DIR}/assets/*.png
    ${CMAKE_CURRENT_SOURCE_DIR}/assets/*.jpg
    ${CMAKE_CURRENT_SOURCE_DIR}/assets/*.ttf)
juce_add_binary_data(SemitonesAssets SOURCES ${SEMITONES_ASSETS})

set(SEMITONES_SOURCES
    PluginProcessor.cpp
    PluginEditor.cpp)

target_sources(Semitones PRIVATE ${SEMITONES_SOURCES})

set(SEMITONES_DEFS
    JUCE_WEB_BROWSER=0
    JUCE_USE_CURL=0
    JUCE_VST3_CAN_REPLACE_VST2=0
    JUCE_DISPLAY_SPLASH_SCREEN=0)

target_compile_definitions(Semitones PUBLIC ${SEMITONES_DEFS})

target_link_libraries(Semitones
    PRIVATE
        SemitonesAssets
        juce::juce_audio_utils
        juce::juce_dsp
    PUBLIC
        juce::juce_recommended_config_flags
        juce::juce_recommended_lto_flags
        juce::juce_recommended_warning_flags)

# ---------------------------------------------------------------------------
# Offline tool (Linux): renders the editor to PNG and runs the audio checks.
option(SEMITONES_BUILD_RENDER "Build the offline render / test tool" OFF)
if(SEMITONES_BUILD_RENDER)
    juce_add_console_app(SemitonesRender PRODUCT_NAME "SemitonesRender")
    juce_generate_juce_header(SemitonesRender)
    target_sources(SemitonesRender PRIVATE tools/render_main.cpp ${SEMITONES_SOURCES})
    target_include_directories(SemitonesRender PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
    target_compile_definitions(SemitonesRender PRIVATE ${SEMITONES_DEFS}
        JUCE_USE_XRANDR=0 JUCE_USE_XINERAMA=0 JUCE_USE_XCURSOR=0 JUCE_USE_XSHM=0
        JucePlugin_Name="Semitones" JucePlugin_IsSynth=0 JucePlugin_WantsMidiInput=1
        JucePlugin_ProducesMidiOutput=0 JucePlugin_IsMidiEffect=0)
    target_link_libraries(SemitonesRender PRIVATE SemitonesAssets
        juce::juce_audio_utils juce::juce_dsp juce::juce_recommended_config_flags)
endif()
