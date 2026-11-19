from fontain.sources.nerdfonts import parse_checksums, parse_index


def test_parse_index():
    release = {
        "tag_name": "v3.5.1",
        "assets": [
            {"name": "JetBrainsMono.tar.xz", "browser_download_url": "https://dl/JetBrainsMono.tar.xz"},
            {"name": "JetBrainsMono.zip", "browser_download_url": "https://dl/JetBrainsMono.zip"},
            {"name": "SHA-256.txt", "browser_download_url": "https://dl/SHA-256.txt"},
        ],
    }
    (e,) = parse_index(release)
    assert e.key == "nerd:JetBrainsMono"
    assert e.extra["checksums"] == "https://dl/SHA-256.txt"
    assert e.version == "v3.5.1"


def test_parse_checksums():
    assert parse_checksums("ABC  a.tar.xz\nbad line here x\n") == {"a.tar.xz": "abc"}
