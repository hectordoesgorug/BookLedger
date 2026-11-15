from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)


def build_version_info(version: str) -> VSVersionInfo:
    parts = tuple(int(part) for part in version.split("."))
    if len(parts) != 3 or any(part < 0 or part > 0xFFFF for part in parts):
        raise ValueError(f"Expected a three-part numeric version, got {version!r}.")
    resource_version = (*parts, 0)
    return VSVersionInfo(
        ffi=FixedFileInfo(filevers=resource_version, prodvers=resource_version),
        kids=[
            StringFileInfo(
                [
                    StringTable(
                        "040904B0",
                        [
                            StringStruct("FileDescription", "BookLedger book collection manager"),
                            StringStruct("FileVersion", version),
                            StringStruct("InternalName", "BookLedger"),
                            StringStruct("OriginalFilename", "BookLedger.exe"),
                            StringStruct("ProductName", "BookLedger"),
                            StringStruct("ProductVersion", version),
                        ],
                    )
                ]
            ),
            VarFileInfo([VarStruct("Translation", [1033, 1200])]),
        ],
    )
