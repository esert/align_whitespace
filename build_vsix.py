#!/usr/bin/env python3
"""Build a minimal VSIX package without requiring Node tooling."""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
FILES = [
    "package.json",
    "extension.js",
    "README.md",
    "python/align_cpp_block.py",
]


def load_package() -> dict:
    return json.loads((ROOT / "package.json").read_text())


def build_content_types() -> str:
    return dedent(
        """\
        <?xml version="1.0" encoding="utf-8"?>
        <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
          <Default Extension="json" ContentType="application/json" />
          <Default Extension="js" ContentType="application/javascript" />
          <Default Extension="md" ContentType="text/markdown" />
          <Default Extension="py" ContentType="text/x-python" />
          <Default Extension="txt" ContentType="text/plain" />
          <Default Extension="vsixmanifest" ContentType="text/xml" />
          <Default Extension="xml" ContentType="text/xml" />
        </Types>
        """
    )


def xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def build_vsix_manifest(package: dict) -> str:
    description = xml_escape(package["description"])
    display_name = xml_escape(package["displayName"])
    extension_name = xml_escape(package["name"])
    publisher = xml_escape(package["publisher"])
    version = xml_escape(package["version"])
    engine = xml_escape(package["engines"]["vscode"])
    categories = ",".join(package.get("categories", []))
    tags = ",".join(package.get("keywords", []))

    return dedent(
        f"""\
        <?xml version="1.0" encoding="utf-8"?>
        <PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011" xmlns:d="http://schemas.microsoft.com/developer/vsx-schema-design/2011">
          <Metadata>
            <Identity Language="en-US" Id="{extension_name}" Version="{version}" Publisher="{publisher}" />
            <DisplayName>{display_name}</DisplayName>
            <Description xml:space="preserve">{description}</Description>
            <Tags>{xml_escape(tags)}</Tags>
            <Categories>{xml_escape(categories)}</Categories>
            <GalleryFlags>Public</GalleryFlags>
            <Properties>
              <Property Id="Microsoft.VisualStudio.Code.Engine" Value="{engine}" />
              <Property Id="Microsoft.VisualStudio.Code.ExtensionDependencies" Value="" />
              <Property Id="Microsoft.VisualStudio.Code.ExtensionPack" Value="" />
              <Property Id="Microsoft.VisualStudio.Code.ExtensionKind" Value="workspace" />
              <Property Id="Microsoft.VisualStudio.Code.LocalizedLanguages" Value="" />
              <Property Id="Microsoft.VisualStudio.Code.ExecutesCode" Value="true" />
              <Property Id="Microsoft.VisualStudio.Services.GitHubFlavoredMarkdown" Value="true" />
              <Property Id="Microsoft.VisualStudio.Services.Content.Pricing" Value="Free" />
            </Properties>
          </Metadata>
          <Installation>
            <InstallationTarget Id="Microsoft.VisualStudio.Code" />
          </Installation>
          <Dependencies />
          <Assets>
            <Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true" />
            <Asset Type="Microsoft.VisualStudio.Services.Content.Details" Path="extension/README.md" Addressable="true" />
          </Assets>
        </PackageManifest>
        """
    )


def main() -> int:
    package = load_package()
    DIST.mkdir(exist_ok=True)

    artifact = DIST / f"{package['name']}-{package['version']}.vsix"
    if artifact.exists():
        artifact.unlink()

    with ZipFile(artifact, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", build_content_types())
        archive.writestr("extension.vsixmanifest", build_vsix_manifest(package))

        for relative in FILES:
            archive.write(ROOT / relative, f"extension/{relative}")

    print(artifact)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
