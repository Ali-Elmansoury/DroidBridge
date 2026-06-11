"""Tests for droidbridge.modules.whatsapp - Module 4: WhatsApp Toolkit (analysis)."""

from datetime import datetime
from unittest.mock import MagicMock

from droidbridge.modules import transfer as transfer_module
from droidbridge.modules import whatsapp

WA_MEDIA = "/sdcard/Android/media/com.whatsapp/WhatsApp/Media"

SCAN_FIND_OUTPUT = (
    f"{WA_MEDIA}/WhatsApp Images/IMG-20230101-WA0001.jpg\t1000\t1672531200.0\n"
    f"{WA_MEDIA}/WhatsApp Images/Sent/IMG-20230102-WA0002.jpg\t2000\t1672617600.0\n"
    f"{WA_MEDIA}/WhatsApp Images/Private/IMG-20230103-WA0003.jpg\t500\t1672704000.0\n"
    f"{WA_MEDIA}/WhatsApp Voice Notes/202301/PTT-20230101-WA0001.opus\t300\t1672531200.0\n"
    f"{WA_MEDIA}/WallPaper/wallpaper1.jpg\t5000\t1672531200.0\n"
)


def make_client(*shell_outputs):
    client = MagicMock()
    client.shell.side_effect = list(shell_outputs)
    return client


class TestDetectInstalls:
    def test_detects_whatsapp_on_modern_path(self):
        client = make_client("1\n0\n0\n0\n")

        installs = whatsapp.detect_installs(client, "SERIAL")

        assert installs == [
            whatsapp.WhatsAppInstall(
                package="com.whatsapp",
                label="WhatsApp",
                base_path="/sdcard/Android/media/com.whatsapp/WhatsApp",
            )
        ]
        assert installs[0].media_path == "/sdcard/Android/media/com.whatsapp/WhatsApp/Media"

    def test_detects_both_whatsapp_and_business(self):
        client = make_client("1\n0\n1\n0\n")

        installs = whatsapp.detect_installs(client, "SERIAL")

        assert [i.package for i in installs] == ["com.whatsapp", "com.whatsapp.w4b"]
        assert installs[1].base_path == "/sdcard/Android/media/com.whatsapp.w4b/WhatsApp Business"

    def test_falls_back_to_legacy_path_when_modern_missing(self):
        client = make_client("0\n1\n0\n0\n")

        installs = whatsapp.detect_installs(client, "SERIAL")

        assert installs == [
            whatsapp.WhatsAppInstall(
                package="com.whatsapp", label="WhatsApp", base_path="/sdcard/WhatsApp"
            )
        ]

    def test_returns_empty_when_neither_installed(self):
        client = make_client("0\n0\n0\n0\n")

        assert whatsapp.detect_installs(client, "SERIAL") == []

    def test_single_shell_call(self):
        client = make_client("1\n0\n0\n0\n")

        whatsapp.detect_installs(client, "SERIAL")

        assert client.shell.call_count == 1


WA_INSTALL = whatsapp.WhatsAppInstall(
    package="com.whatsapp", label="WhatsApp", base_path="/sdcard/Android/media/com.whatsapp/WhatsApp"
)

W4B_INSTALL = whatsapp.WhatsAppInstall(
    package="com.whatsapp.w4b",
    label="WhatsApp Business",
    base_path="/sdcard/Android/media/com.whatsapp.w4b/WhatsApp Business",
)


class TestScanMedia:
    def test_classifies_folder_type_and_section(self):
        client = make_client(SCAN_FIND_OUTPUT)

        files = whatsapp.scan_media(client, "SERIAL", WA_INSTALL)

        assert len(files) == 5
        by_path = {f.path: f for f in files}

        received = by_path[f"{WA_MEDIA}/WhatsApp Images/IMG-20230101-WA0001.jpg"]
        assert received.folder_type == "Images"
        assert received.section == "Received"
        assert received.extension == "jpg"
        assert received.size == 1000
        assert received.mtime == datetime.fromtimestamp(1672531200.0)

        sent = by_path[f"{WA_MEDIA}/WhatsApp Images/Sent/IMG-20230102-WA0002.jpg"]
        assert sent.folder_type == "Images"
        assert sent.section == "Sent"

        private = by_path[f"{WA_MEDIA}/WhatsApp Images/Private/IMG-20230103-WA0003.jpg"]
        assert private.folder_type == "Images"
        assert private.section == "Private"

        voice = by_path[f"{WA_MEDIA}/WhatsApp Voice Notes/202301/PTT-20230101-WA0001.opus"]
        assert voice.folder_type == "Voice Notes"
        assert voice.section == "Received"

        wallpaper = by_path[f"{WA_MEDIA}/WallPaper/wallpaper1.jpg"]
        assert wallpaper.folder_type == "WallPaper"
        assert wallpaper.section == "Received"

    def test_strips_business_label_prefix(self):
        business_media = f"{W4B_INSTALL.base_path}/Media"
        client = make_client(f"{business_media}/WhatsApp Business Images/photo.jpg\t100\t1672531200.0\n")

        files = whatsapp.scan_media(client, "SERIAL", W4B_INSTALL)

        assert files[0].folder_type == "Images"

    def test_classifies_loose_files_in_media_root_as_other(self):
        client = make_client(f"{WA_MEDIA}/IMG-20250205-WA0023.jpeg\t1000\t1672531200.0\n")

        files = whatsapp.scan_media(client, "SERIAL", WA_INSTALL)

        assert files[0].folder_type == "Other"
        assert files[0].section == "Received"

    def test_excludes_hidden_dot_folders(self):
        output = (
            f"{WA_MEDIA}/WhatsApp Images/IMG-20230101-WA0001.jpg\t1000\t1672531200.0\n"
            f"{WA_MEDIA}/.Statuses/status1.jpg\t500\t1672531200.0\n"
            f"{WA_MEDIA}/.Shared/.thumb.jpg\t200\t1672531200.0\n"
        )
        client = make_client(output)

        files = whatsapp.scan_media(client, "SERIAL", WA_INSTALL)

        assert len(files) == 1
        assert files[0].folder_type == "Images"


class TestSummarizeByFolder:
    def _file(self, folder_type, section, size):
        return whatsapp.MediaFile(
            path="/x", size=size, mtime=datetime.fromtimestamp(0), folder_type=folder_type, section=section
        )

    def test_groups_by_folder_type_and_section(self):
        files = [
            self._file("Images", "Received", 1000),
            self._file("Images", "Sent", 2000),
            self._file("Images", "Received", 500),
        ]

        summary = whatsapp.summarize_by_folder(files)

        assert summary == [
            whatsapp.FolderSummary(folder_type="Images", section="Received", file_count=2, total_size=1500),
            whatsapp.FolderSummary(folder_type="Images", section="Sent", file_count=1, total_size=2000),
        ]

    def test_orders_sections_received_sent_private(self):
        files = [
            self._file("Images", "Private", 1),
            self._file("Images", "Sent", 1),
            self._file("Images", "Received", 1),
        ]

        summary = whatsapp.summarize_by_folder(files)

        assert [s.section for s in summary] == ["Received", "Sent", "Private"]

    def test_orders_folder_types_alphabetically(self):
        files = [self._file("Video", "Received", 1), self._file("Images", "Received", 1)]

        summary = whatsapp.summarize_by_folder(files)

        assert [s.folder_type for s in summary] == ["Images", "Video"]


WA_STATUSES = f"{WA_MEDIA}/.Statuses"
W4B_STATUSES = f"{W4B_INSTALL.media_path}/.Statuses"


class TestListStatuses:
    def test_lists_image_and_video_status_files(self):
        find_output = (
            f"{WA_STATUSES}/IMG-status1.jpg\t1000\t1672531200.0\n"
            f"{WA_STATUSES}/VID-status2.mp4\t5000\t1672531300.0\n"
            f"{WA_STATUSES}/.nomedia\t0\t1672531100.0\n"
        )
        client = make_client("1\n", find_output)

        statuses = whatsapp.list_statuses(client, "SERIAL", WA_INSTALL)

        assert [s.path for s in statuses] == [
            f"{WA_STATUSES}/IMG-status1.jpg",
            f"{WA_STATUSES}/VID-status2.mp4",
        ]
        assert statuses[0].size == 1000
        assert statuses[1].size == 5000

    def test_returns_empty_when_no_statuses_folder(self):
        client = make_client("0\n")

        statuses = whatsapp.list_statuses(client, "SERIAL", WA_INSTALL)

        assert statuses == []
        assert client.shell.call_count == 1


class TestPlanSaveStatuses:
    def test_builds_per_app_status_subfolders(self, tmp_path):
        client = make_client(
            "1\n",
            f"{WA_STATUSES}/status1.jpg\t1000\t1672531200.0\n",
            "1\n",
            f"{W4B_STATUSES}/status2.mp4\t2000\t1672531300.0\n",
        )

        plan = whatsapp.plan_save_statuses(client, "SERIAL", [WA_INSTALL, W4B_INSTALL], str(tmp_path))

        dests = {item.source: item.dest for item in plan.items}
        assert dests[f"{WA_STATUSES}/status1.jpg"] == str(tmp_path / "WhatsApp" / "Statuses" / "status1.jpg")
        assert dests[f"{W4B_STATUSES}/status2.mp4"] == str(
            tmp_path / "WhatsApp Business" / "Statuses" / "status2.mp4"
        )
        assert all(item.action == transfer_module.ACTION_COPY for item in plan.items)

    def test_returns_empty_plan_when_no_statuses(self, tmp_path):
        client = make_client("0\n", "0\n")

        plan = whatsapp.plan_save_statuses(client, "SERIAL", [WA_INSTALL, W4B_INSTALL], str(tmp_path))

        assert plan.items == []
        assert plan.total_files == 0
