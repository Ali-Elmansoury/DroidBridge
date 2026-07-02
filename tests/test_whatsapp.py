# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Tests for droidbridge.modules.whatsapp - Module 4: WhatsApp Toolkit (analysis)."""

import shlex
from datetime import date, datetime
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


class TestMediaFileYearMonth:
    def _file(self, path):
        return whatsapp.MediaFile(
            path=path, size=1, mtime=datetime.fromtimestamp(0), folder_type="Images", section="Received"
        )

    def test_parses_year_month_from_img_filename(self):
        f = self._file(f"{WA_MEDIA}/WhatsApp Images/IMG-20230115-WA0001.jpg")
        assert f.year_month == "2023-01"

    def test_parses_year_month_from_voice_note_filename(self):
        f = self._file(f"{WA_MEDIA}/WhatsApp Voice Notes/202101/PTT-20210615-WA0002.opus")
        assert f.year_month == "2021-06"

    def test_unknown_for_filename_without_date_pattern(self):
        f = self._file(f"{WA_MEDIA}/WallPaper/wallpaper1.jpg")
        assert f.year_month == "Unknown"

    def test_unknown_for_year_out_of_range(self):
        f = self._file(f"{WA_MEDIA}/WhatsApp Documents/DOC-19990101-WA0001.pdf")
        assert f.year_month == "Unknown"

    def test_unknown_for_invalid_month(self):
        f = self._file(f"{WA_MEDIA}/WhatsApp Images/IMG-20231399-WA0001.jpg")
        assert f.year_month == "Unknown"


class TestSummarizeByYearMonth:
    def _file(self, path, size=1):
        return whatsapp.MediaFile(
            path=path, size=size, mtime=datetime.fromtimestamp(0), folder_type="Images", section="Received"
        )

    def test_groups_and_aggregates_by_year_month(self):
        files = [
            self._file(f"{WA_MEDIA}/WhatsApp Images/IMG-20230102-WA0001.jpg", size=1000),
            self._file(f"{WA_MEDIA}/WhatsApp Images/IMG-20230115-WA0002.jpg", size=500),
            self._file(f"{WA_MEDIA}/WhatsApp Images/IMG-20221225-WA0003.jpg", size=2000),
        ]

        summary = whatsapp.summarize_by_year_month(files)

        assert summary == [
            whatsapp.YearMonthSummary(year_month="2022-12", file_count=1, total_size=2000),
            whatsapp.YearMonthSummary(year_month="2023-01", file_count=2, total_size=1500),
        ]

    def test_unknown_dates_sorted_last(self):
        files = [
            self._file(f"{WA_MEDIA}/WallPaper/wallpaper1.jpg"),
            self._file(f"{WA_MEDIA}/WhatsApp Images/IMG-20230102-WA0001.jpg"),
        ]

        summary = whatsapp.summarize_by_year_month(files)

        assert [s.year_month for s in summary] == ["2023-01", "Unknown"]


class TestSummarizeByExtension:
    def _file(self, path, size=1):
        return whatsapp.MediaFile(
            path=path, size=size, mtime=datetime.fromtimestamp(0), folder_type="Images", section="Received"
        )

    def test_groups_and_aggregates_by_extension(self):
        files = [
            self._file(f"{WA_MEDIA}/WhatsApp Images/IMG-1.jpg", size=1000),
            self._file(f"{WA_MEDIA}/WhatsApp Images/IMG-2.jpg", size=500),
            self._file(f"{WA_MEDIA}/WhatsApp Video/VID-1.mp4", size=2000),
        ]

        summary = whatsapp.summarize_by_extension(files)

        assert summary == [
            whatsapp.ExtensionSummary(extension="jpg", file_count=2, total_size=1500),
            whatsapp.ExtensionSummary(extension="mp4", file_count=1, total_size=2000),
        ]

    def test_orders_extensions_alphabetically(self):
        files = [self._file(f"{WA_MEDIA}/x.png"), self._file(f"{WA_MEDIA}/x.jpg")]

        summary = whatsapp.summarize_by_extension(files)

        assert [s.extension for s in summary] == ["jpg", "png"]


class TestMediaFileDate:
    def _file(self, path):
        return whatsapp.MediaFile(
            path=path, size=1, mtime=datetime.fromtimestamp(0), folder_type="Images", section="Received"
        )

    def test_parses_date_from_filename(self):
        f = self._file(f"{WA_MEDIA}/WhatsApp Images/IMG-20230115-WA0001.jpg")
        assert f.date == date(2023, 1, 15)

    def test_date_is_none_for_filename_without_date_pattern(self):
        f = self._file(f"{WA_MEDIA}/WallPaper/wallpaper1.jpg")
        assert f.date is None

    def test_date_is_none_for_year_out_of_range(self):
        f = self._file(f"{WA_MEDIA}/WhatsApp Documents/DOC-19990101-WA0001.pdf")
        assert f.date is None

    def test_date_is_none_for_invalid_month_or_day(self):
        f = self._file(f"{WA_MEDIA}/WhatsApp Images/IMG-20231399-WA0001.jpg")
        assert f.date is None


class TestSummarizeByCutoff:
    def _file(self, path, size=1, folder_type="Images"):
        return whatsapp.MediaFile(
            path=path, size=size, mtime=datetime.fromtimestamp(0), folder_type=folder_type, section="Received"
        )

    def test_splits_pre_post_and_unknown_by_folder_type(self):
        files = [
            self._file(f"{WA_MEDIA}/WhatsApp Images/IMG-20230101-WA0001.jpg", size=1000),
            self._file(f"{WA_MEDIA}/WhatsApp Images/IMG-20241001-WA0002.jpg", size=2000),
            self._file(f"{WA_MEDIA}/WallPaper/wallpaper1.jpg", size=500, folder_type="WallPaper"),
        ]

        summary = whatsapp.summarize_by_cutoff(files, date(2024, 9, 1))

        assert summary == [
            whatsapp.CutoffSummary(
                folder_type="Images",
                pre_count=1, pre_size=1000,
                post_count=1, post_size=2000,
                unknown_count=0, unknown_size=0,
            ),
            whatsapp.CutoffSummary(
                folder_type="WallPaper",
                pre_count=0, pre_size=0,
                post_count=0, post_size=0,
                unknown_count=1, unknown_size=500,
            ),
        ]

    def test_orders_folder_types_alphabetically(self):
        files = [
            self._file(f"{WA_MEDIA}/x.jpg", folder_type="Video"),
            self._file(f"{WA_MEDIA}/x.jpg", folder_type="Images"),
        ]

        summary = whatsapp.summarize_by_cutoff(files, date(2024, 9, 1))

        assert [s.folder_type for s in summary] == ["Images", "Video"]

    def test_file_on_cutoff_date_is_post_cutoff(self):
        files = [self._file(f"{WA_MEDIA}/WhatsApp Images/IMG-20240901-WA0001.jpg")]

        summary = whatsapp.summarize_by_cutoff(files, date(2024, 9, 1))

        assert summary[0].pre_count == 0
        assert summary[0].post_count == 1


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


class TestPlanBackup:
    def test_full_backup_mirrors_media_structure(self, tmp_path):
        client = make_client(SCAN_FIND_OUTPUT)

        plan = whatsapp.plan_backup(client, "SERIAL", [WA_INSTALL], str(tmp_path))

        assert plan.total_files == 5
        dests = {item.source: item.dest for item in plan.items}
        assert dests[f"{WA_MEDIA}/WhatsApp Images/IMG-20230101-WA0001.jpg"] == str(
            tmp_path / "WhatsApp" / "Media" / "WhatsApp Images" / "IMG-20230101-WA0001.jpg"
        )
        assert dests[f"{WA_MEDIA}/WhatsApp Images/Sent/IMG-20230102-WA0002.jpg"] == str(
            tmp_path / "WhatsApp" / "Media" / "WhatsApp Images" / "Sent" / "IMG-20230102-WA0002.jpg"
        )
        assert dests[f"{WA_MEDIA}/WallPaper/wallpaper1.jpg"] == str(
            tmp_path / "WhatsApp" / "Media" / "WallPaper" / "wallpaper1.jpg"
        )

    def test_selective_backup_filters_by_folder_type(self, tmp_path):
        client = make_client(SCAN_FIND_OUTPUT)

        plan = whatsapp.plan_backup(client, "SERIAL", [WA_INSTALL], str(tmp_path), types={"Images"})

        assert plan.total_files == 3
        assert all("WhatsApp Images" in item.source for item in plan.items)

    def test_returns_empty_plan_when_no_media(self, tmp_path):
        client = make_client("")

        plan = whatsapp.plan_backup(client, "SERIAL", [WA_INSTALL], str(tmp_path))

        assert plan.items == []
        assert plan.total_files == 0


class TestPlanRestore:
    def test_pushes_backup_folder_onto_media_path(self, tmp_path):
        media_dir = tmp_path / "WhatsApp" / "Media" / "WhatsApp Images"
        media_dir.mkdir(parents=True)
        (media_dir / "IMG-20230101-WA0001.jpg").write_bytes(b"x" * 1000)
        client = make_client("NO\n")

        plan = whatsapp.plan_restore(client, "SERIAL", WA_INSTALL, str(tmp_path))

        assert plan.direction == "push"
        assert plan.total_files == 1
        assert plan.items[0].dest == f"{WA_INSTALL.media_path}/WhatsApp Images/IMG-20230101-WA0001.jpg"

    def test_returns_empty_plan_when_no_backup_folder(self, tmp_path):
        client = make_client()

        plan = whatsapp.plan_restore(client, "SERIAL", WA_INSTALL, str(tmp_path))

        assert plan.items == []
        assert client.shell.call_count == 0


class TestPlanOrganizeByDate:
    def test_unsectioned_groups_by_year_month_and_unknown(self, tmp_path):
        src = tmp_path / "WhatsApp" / "Media" / "WhatsApp Voice Notes"
        nested = src / "202301"
        nested.mkdir(parents=True)
        (nested / "PTT-20230115-WA0001.opus").write_bytes(b"x")
        (src / "weird_name.opus").write_bytes(b"y")

        plan = whatsapp.plan_organize_by_date(str(src), sectioned=False)

        dests = {item.source: item.dest for item in plan.items}
        organized = src.parent / "WhatsApp_Voice_Notes_Organized"
        assert dests[str(nested / "PTT-20230115-WA0001.opus")] == str(
            organized / "2023" / "01-Jan" / "PTT-20230115-WA0001.opus"
        )
        assert dests[str(src / "weird_name.opus")] == str(organized / "Unknown" / "weird_name.opus")

    def test_sectioned_groups_by_section_then_year_month(self, tmp_path):
        src = tmp_path / "WhatsApp" / "Media" / "WhatsApp Images"
        sent = src / "Sent"
        private = src / "Private"
        sent.mkdir(parents=True)
        private.mkdir(parents=True)
        (src / "IMG-20230101-WA0001.jpg").write_bytes(b"x")
        (sent / "IMG-20230102-WA0002.jpg").write_bytes(b"y")
        (private / "IMG-20230103-WA0003.jpg").write_bytes(b"z")

        plan = whatsapp.plan_organize_by_date(str(src))

        dests = {item.source: item.dest for item in plan.items}
        organized = src.parent / "WhatsApp_Images_Organized"
        assert dests[str(src / "IMG-20230101-WA0001.jpg")] == str(
            organized / "Received" / "2023" / "01-Jan" / "IMG-20230101-WA0001.jpg"
        )
        assert dests[str(sent / "IMG-20230102-WA0002.jpg")] == str(
            organized / "Sent" / "2023" / "01-Jan" / "IMG-20230102-WA0002.jpg"
        )
        assert dests[str(private / "IMG-20230103-WA0003.jpg")] == str(
            organized / "Private" / "2023" / "01-Jan" / "IMG-20230103-WA0003.jpg"
        )

    def test_ignores_misleading_folder_name_and_uses_filename_date(self, tmp_path):
        # spec §4.5: "Detect and fix files placed in wrong year folders" - the
        # destination is derived from the filename's date, not from whatever
        # folder the file currently sits in.
        src = tmp_path / "WhatsApp" / "Media" / "WhatsApp Voice Notes"
        wrong_folder = src / "9999"
        wrong_folder.mkdir(parents=True)
        (wrong_folder / "PTT-20220615-WA0001.opus").write_bytes(b"x")

        plan = whatsapp.plan_organize_by_date(str(src), sectioned=False)

        dests = {item.source: item.dest for item in plan.items}
        organized = src.parent / "WhatsApp_Voice_Notes_Organized"
        assert dests[str(wrong_folder / "PTT-20220615-WA0001.opus")] == str(
            organized / "2022" / "06-Jun" / "PTT-20220615-WA0001.opus"
        )

    def test_routes_out_of_range_year_to_unknown(self, tmp_path):
        # spec §4.5: validate year range (2009-2030) to reject false date
        # matches (e.g. student IDs / serial numbers mistaken as dates).
        src = tmp_path / "WhatsApp" / "Media" / "WhatsApp Voice Notes"
        src.mkdir(parents=True)
        (src / "PTT-19991231-WA0001.opus").write_bytes(b"x")

        plan = whatsapp.plan_organize_by_date(str(src), sectioned=False)

        dests = {item.source: item.dest for item in plan.items}
        organized = src.parent / "WhatsApp_Voice_Notes_Organized"
        assert dests[str(src / "PTT-19991231-WA0001.opus")] == str(
            organized / "Unknown" / "PTT-19991231-WA0001.opus"
        )

    def test_resolves_destination_filename_collisions(self, tmp_path):
        src = tmp_path / "WhatsApp" / "Media" / "WhatsApp Voice Notes"
        a = src / "a"
        b = src / "b"
        a.mkdir(parents=True)
        b.mkdir(parents=True)
        (a / "PTT-20230101-WA0001.opus").write_bytes(b"x")
        (b / "PTT-20230101-WA0001.opus").write_bytes(b"y")

        plan = whatsapp.plan_organize_by_date(str(src), sectioned=False)

        dests = {item.dest for item in plan.items}
        assert len(dests) == 2


class TestPlanOrganizeDocuments:
    def test_groups_by_section_then_category_then_date(self, tmp_path):
        src = tmp_path / "WhatsApp" / "Media" / "WhatsApp Documents"
        sent = src / "Sent"
        sent.mkdir(parents=True)
        (src / "DOC-20230101-WA0001.pdf").write_bytes(b"x")
        (sent / "DOC-20230102-WA0002.xlsx").write_bytes(b"y")

        plan = whatsapp.plan_organize_documents(str(src))

        dests = {item.source: item.dest for item in plan.items}
        organized = src.parent / "WhatsApp_Documents_Organized"
        assert dests[str(src / "DOC-20230101-WA0001.pdf")] == str(
            organized / "Received" / "PDFs" / "2023" / "01-Jan" / "DOC-20230101-WA0001.pdf"
        )
        assert dests[str(sent / "DOC-20230102-WA0002.xlsx")] == str(
            organized / "Sent" / "Spreadsheets" / "2023" / "01-Jan" / "DOC-20230102-WA0002.xlsx"
        )

    def test_files_without_date_go_to_original_files(self, tmp_path):
        src = tmp_path / "WhatsApp" / "Media" / "WhatsApp Documents"
        src.mkdir(parents=True)
        (src / "main.py").write_bytes(b"x")

        plan = whatsapp.plan_organize_documents(str(src))

        dests = {item.source: item.dest for item in plan.items}
        organized = src.parent / "WhatsApp_Documents_Organized"
        assert dests[str(src / "main.py")] == str(
            organized / "Received" / "Source_Code" / "Original_Files" / "main.py"
        )

    def test_unrecognized_extension_goes_to_other(self, tmp_path):
        src = tmp_path / "WhatsApp" / "Media" / "WhatsApp Documents"
        src.mkdir(parents=True)
        (src / "DOC-20230101-WA0001.xyz").write_bytes(b"x")

        plan = whatsapp.plan_organize_documents(str(src))

        dests = {item.source: item.dest for item in plan.items}
        organized = src.parent / "WhatsApp_Documents_Organized"
        assert dests[str(src / "DOC-20230101-WA0001.xyz")] == str(
            organized / "Received" / "Other" / "2023" / "01-Jan" / "DOC-20230101-WA0001.xyz"
        )


class TestFixFilenames:
    def test_fixes_double_dot_filename(self, tmp_path):
        (tmp_path / "Sheet..pdf").write_bytes(b"%PDF-1.4")

        renames = whatsapp.fix_filenames(str(tmp_path))

        assert not (tmp_path / "Sheet..pdf").exists()
        assert (tmp_path / "Sheet.pdf").exists()
        assert renames == [(str(tmp_path / "Sheet..pdf"), str(tmp_path / "Sheet.pdf"))]

    def test_adds_extension_sniffed_from_magic_bytes(self, tmp_path):
        (tmp_path / "DOC-20220310-WA0001.").write_bytes(b"%PDF-1.4")

        renames = whatsapp.fix_filenames(str(tmp_path))

        assert not (tmp_path / "DOC-20220310-WA0001.").exists()
        assert (tmp_path / "DOC-20220310-WA0001.pdf").exists()
        assert renames == [
            (str(tmp_path / "DOC-20220310-WA0001."), str(tmp_path / "DOC-20220310-WA0001.pdf"))
        ]

    def test_leaves_recognized_extensions_unchanged(self, tmp_path):
        (tmp_path / "IMG-20230101-WA0001.jpg").write_bytes(b"\xff\xd8\xff\xe0")

        renames = whatsapp.fix_filenames(str(tmp_path))

        assert renames == []
        assert (tmp_path / "IMG-20230101-WA0001.jpg").exists()

    def test_leaves_unrecognized_extensionless_files_unchanged(self, tmp_path):
        (tmp_path / "mystery_file").write_bytes(b"not a known signature")

        renames = whatsapp.fix_filenames(str(tmp_path))

        assert renames == []
        assert (tmp_path / "mystery_file").exists()

    def test_resolves_rename_collisions(self, tmp_path):
        (tmp_path / "Sheet.pdf").write_bytes(b"existing")
        (tmp_path / "Sheet..pdf").write_bytes(b"%PDF-1.4")

        renames = whatsapp.fix_filenames(str(tmp_path))

        assert renames == [(str(tmp_path / "Sheet..pdf"), str(tmp_path / "Sheet_1.pdf"))]
        assert (tmp_path / "Sheet_1.pdf").read_bytes() == b"%PDF-1.4"


class TestExecuteOrganizePlan:
    def test_moves_files_to_destinations(self, tmp_path):
        src = tmp_path / "PTT-20230101-WA0001.opus"
        src.write_bytes(b"x")
        dest = tmp_path / "2023" / "01-Jan" / "PTT-20230101-WA0001.opus"

        plan = whatsapp.OrganizePlan(items=[whatsapp.OrganizeItem(source=str(src), dest=str(dest))])
        whatsapp.execute_organize_plan(plan)

        assert not src.exists()
        assert dest.read_bytes() == b"x"


class TestPlanDelete:
    def _file(self, path, folder_type="Images", section="Received", size=1000):
        return whatsapp.MediaFile(
            path=path, size=size, mtime=datetime.fromtimestamp(0), folder_type=folder_type, section=section
        )

    def test_deletes_files_dated_before_cutoff(self):
        old = self._file(f"{WA_MEDIA}/WhatsApp Images/IMG-20230101-WA0001.jpg")
        new = self._file(f"{WA_MEDIA}/WhatsApp Images/IMG-20250101-WA0001.jpg")

        plan = whatsapp.plan_delete([old, new], before=date(2024, 9, 1))

        assert plan.to_delete == [old]
        assert plan.kept == [new]

    def test_total_files_and_bytes_reflect_to_delete_only(self):
        old = self._file(f"{WA_MEDIA}/WhatsApp Images/IMG-20230101-WA0001.jpg", size=1000)
        new = self._file(f"{WA_MEDIA}/WhatsApp Images/IMG-20250101-WA0001.jpg", size=2000)

        plan = whatsapp.plan_delete([old, new], before=date(2024, 9, 1))

        assert plan.total_files == 1
        assert plan.total_bytes == 1000

    def test_keeps_files_with_no_parseable_date_regardless_of_cutoff(self):
        unknown = self._file(f"{WA_MEDIA}/WallPaper/wallpaper1.jpg", folder_type="WallPaper")

        plan = whatsapp.plan_delete([unknown], before=date(2030, 1, 1))

        assert plan.to_delete == []
        assert plan.kept == [unknown]

    def test_keep_types_are_excluded_from_deletion(self):
        old_image = self._file(f"{WA_MEDIA}/WhatsApp Images/IMG-20230101-WA0001.jpg", folder_type="Images")
        old_doc = self._file(
            f"{WA_MEDIA}/WhatsApp Documents/DOC-20230101-WA0001.pdf", folder_type="Documents"
        )

        plan = whatsapp.plan_delete([old_image, old_doc], before=date(2024, 9, 1), keep_types={"Images"})

        assert plan.to_delete == [old_doc]
        assert plan.kept == [old_image]


class TestVerifyBackupExists:
    def _file(self, path, size=1000):
        return whatsapp.MediaFile(
            path=path, size=size, mtime=datetime.fromtimestamp(0), folder_type="Images", section="Received"
        )

    def test_returns_empty_when_all_files_backed_up_with_matching_size(self, tmp_path):
        media_dir = tmp_path / "WhatsApp" / "Media" / "WhatsApp Images"
        media_dir.mkdir(parents=True)
        (media_dir / "IMG-20230101-WA0001.jpg").write_bytes(b"x" * 1000)
        media_file = self._file(f"{WA_MEDIA}/WhatsApp Images/IMG-20230101-WA0001.jpg", size=1000)

        missing = whatsapp.verify_backup_exists(WA_INSTALL, str(tmp_path), [media_file])

        assert missing == []

    def test_returns_file_missing_from_backup(self, tmp_path):
        media_file = self._file(f"{WA_MEDIA}/WhatsApp Images/IMG-20230101-WA0001.jpg", size=1000)

        missing = whatsapp.verify_backup_exists(WA_INSTALL, str(tmp_path), [media_file])

        assert missing == [media_file]

    def test_returns_file_with_size_mismatch(self, tmp_path):
        media_dir = tmp_path / "WhatsApp" / "Media" / "WhatsApp Images"
        media_dir.mkdir(parents=True)
        (media_dir / "IMG-20230101-WA0001.jpg").write_bytes(b"x" * 500)
        media_file = self._file(f"{WA_MEDIA}/WhatsApp Images/IMG-20230101-WA0001.jpg", size=1000)

        missing = whatsapp.verify_backup_exists(WA_INSTALL, str(tmp_path), [media_file])

        assert missing == [media_file]


class TestExecuteDeletePlan:
    def _file(self, path, size=1):
        return whatsapp.MediaFile(
            path=path, size=size, mtime=datetime.fromtimestamp(0), folder_type="Images", section="Received"
        )

    def test_deletes_files_in_batches(self):
        files = [self._file(f"/sdcard/file{i}.jpg") for i in range(3)]
        plan = whatsapp.DeletePlan(to_delete=files, kept=[])
        client = make_client("", "")

        whatsapp.execute_delete_plan(client, "SERIAL", plan, batch_size=2)

        assert client.shell.call_count == 2

        first_serial, first_command = client.shell.call_args_list[0][0]
        assert first_serial == "SERIAL"
        assert first_command.startswith("rm -f ")
        assert "/sdcard/file0.jpg" in first_command
        assert "/sdcard/file1.jpg" in first_command
        assert "/sdcard/file2.jpg" not in first_command

        _, second_command = client.shell.call_args_list[1][0]
        assert "/sdcard/file2.jpg" in second_command
        assert "/sdcard/file0.jpg" not in second_command

    def test_does_nothing_when_plan_is_empty(self):
        plan = whatsapp.DeletePlan(to_delete=[], kept=[])
        client = make_client()

        whatsapp.execute_delete_plan(client, "SERIAL", plan)

        assert client.shell.call_count == 0

    def test_quotes_paths_with_spaces(self):
        path = f"{WA_MEDIA}/WhatsApp Images/IMG-20230101-WA0001.jpg"
        plan = whatsapp.DeletePlan(to_delete=[self._file(path)], kept=[])
        client = make_client("")

        whatsapp.execute_delete_plan(client, "SERIAL", plan)

        _, command = client.shell.call_args[0]
        assert shlex.quote(path) in command


class TestVerifyDelete:
    def _file(self, path, size=1000):
        return whatsapp.MediaFile(
            path=path, size=size, mtime=datetime.fromtimestamp(0), folder_type="Images", section="Received"
        )

    def test_reports_deleted_and_remaining_after_rescan(self):
        deleted_path = f"{WA_MEDIA}/WhatsApp Images/IMG-20230101-WA0001.jpg"
        remaining_path = f"{WA_MEDIA}/WhatsApp Images/IMG-20230102-WA0002.jpg"
        deleted_file = self._file(deleted_path, size=1000)
        remaining_file = self._file(remaining_path, size=2000)
        plan = whatsapp.DeletePlan(to_delete=[deleted_file, remaining_file], kept=[])

        rescan_output = f"{remaining_path}\t2000\t1672617600.0\n"
        client = make_client(rescan_output)

        result = whatsapp.verify_delete(client, "SERIAL", WA_INSTALL, plan)

        assert result.deleted == 1
        assert result.remaining == [remaining_file]

    def test_all_deleted_when_rescan_finds_nothing(self):
        deleted_file = self._file(f"{WA_MEDIA}/WhatsApp Images/IMG-20230101-WA0001.jpg")
        plan = whatsapp.DeletePlan(to_delete=[deleted_file], kept=[])
        client = make_client("")

        result = whatsapp.verify_delete(client, "SERIAL", WA_INSTALL, plan)

        assert result.deleted == 1
        assert result.remaining == []

    def test_empty_plan_reports_nothing(self):
        plan = whatsapp.DeletePlan(to_delete=[], kept=[])
        client = make_client("")

        result = whatsapp.verify_delete(client, "SERIAL", WA_INSTALL, plan)

        assert result.deleted == 0
        assert result.remaining == []

    def test_after_files_reflects_full_rescan(self):
        deleted_path = f"{WA_MEDIA}/WhatsApp Images/IMG-20230101-WA0001.jpg"
        remaining_path = f"{WA_MEDIA}/WhatsApp Images/IMG-20230102-WA0002.jpg"
        deleted_file = self._file(deleted_path, size=1000)
        remaining_file = self._file(remaining_path, size=2000)
        plan = whatsapp.DeletePlan(to_delete=[deleted_file, remaining_file], kept=[])

        rescan_output = f"{remaining_path}\t2000\t1672617600.0\n"

        result = whatsapp.verify_delete(make_client(rescan_output), "SERIAL", WA_INSTALL, plan)
        expected_after = whatsapp.scan_media(make_client(rescan_output), "SERIAL", WA_INSTALL)

        assert result.after_files == expected_after


class TestIsEncryptedDbFile:
    def test_crypt14_is_encrypted(self):
        assert whatsapp.is_encrypted_db_file("msgstore.db.crypt14") is True

    def test_crypt12_and_crypt15_are_encrypted(self):
        assert whatsapp.is_encrypted_db_file("wa.db.crypt12") is True
        assert whatsapp.is_encrypted_db_file("wa.db.crypt15") is True

    def test_plain_db_is_not_encrypted(self):
        assert whatsapp.is_encrypted_db_file("wa.db") is False

    def test_other_extension_is_not_encrypted(self):
        assert whatsapp.is_encrypted_db_file("backup_settings.json") is False


DB_PATH = f"{WA_INSTALL.base_path}/Databases"
BACKUPS_PATH = f"{WA_INSTALL.base_path}/Backups"
ACCOUNTS_PATH = f"{WA_INSTALL.base_path}/accounts"


class TestPlanBackupDb:
    def test_pulls_databases_backups_and_accounts_folders(self, tmp_path):
        client = make_client(
            "1\n",
            f"{DB_PATH}/msgstore.db.crypt14\t1000\t1672531200.0\n",
            "1\n",
            f"{BACKUPS_PATH}/wa.db.crypt14\t2000\t1672531200.0\n",
            "1\n",
            f"{ACCOUNTS_PATH}/session.bin\t10\t1672531200.0\n",
        )

        plan = whatsapp.plan_backup_db(client, "SERIAL", [WA_INSTALL], str(tmp_path))

        dests = {item.source: item.dest for item in plan.items}
        assert dests[f"{DB_PATH}/msgstore.db.crypt14"] == str(
            tmp_path / "WhatsApp" / "Databases" / "msgstore.db.crypt14"
        )
        assert dests[f"{BACKUPS_PATH}/wa.db.crypt14"] == str(
            tmp_path / "WhatsApp" / "Backups" / "wa.db.crypt14"
        )
        assert dests[f"{ACCOUNTS_PATH}/session.bin"] == str(
            tmp_path / "WhatsApp" / "accounts" / "session.bin"
        )
        assert all(item.action == transfer_module.ACTION_COPY for item in plan.items)

    def test_skips_folders_that_dont_exist(self, tmp_path):
        client = make_client(
            "1\n",
            f"{DB_PATH}/msgstore.db.crypt14\t1000\t1672531200.0\n",
            "0\n",
            "0\n",
        )

        plan = whatsapp.plan_backup_db(client, "SERIAL", [WA_INSTALL], str(tmp_path))

        assert plan.total_files == 1
        assert plan.items[0].source == f"{DB_PATH}/msgstore.db.crypt14"

    def test_preserves_subfolder_structure(self, tmp_path):
        client = make_client(
            "1\n",
            f"{DB_PATH}/msgstore.db.crypt14\t1000\t1672531200.0\n",
            "1\n",
            (
                f"{BACKUPS_PATH}/wa.db.crypt14\t2000\t1672531200.0\n"
                f"{BACKUPS_PATH}/Stickers/sticker1.webp\t300\t1672531200.0\n"
            ),
            "0\n",
        )

        plan = whatsapp.plan_backup_db(client, "SERIAL", [WA_INSTALL], str(tmp_path))

        dests = {item.source: item.dest for item in plan.items}
        assert dests[f"{BACKUPS_PATH}/Stickers/sticker1.webp"] == str(
            tmp_path / "WhatsApp" / "Backups" / "Stickers" / "sticker1.webp"
        )

    def test_returns_empty_plan_when_no_folders_exist(self, tmp_path):
        client = make_client("0\n", "0\n", "0\n")

        plan = whatsapp.plan_backup_db(client, "SERIAL", [WA_INSTALL], str(tmp_path))

        assert plan.items == []
        assert plan.total_files == 0
