
# Create a signals TSV at fileio.path("signals list") with only the header row.
signals_list.new()

build_utils.run_macro(
    "build_rackmount_enclosure",
    "macros/device_artifacts",
    "https://github.com/harnice/harnice-general-library",
    artifact_id="body-1",
    depth=configuration["depth"],
    units=configuration["U"],
)

