# DroidBridge build automation
# Usage:
#   make release          — regenerate docs + rebuild PyInstaller + package Linux release
#   make docs             — only regenerate the .docx project document
#   make build            — only run PyInstaller (no docs, no packaging)
#   make package          — only package an existing dist/ into releases/
#   make clean            — remove build/ dist/ artefacts (keeps releases/)

VERSION ?= $(shell git describe --tags --abbrev=0 2>/dev/null | sed 's/^v//' || echo "1.0.0")

.PHONY: release docs build package clean

release: docs build package

docs:
	@echo "[docs] Regenerating documents (.docx + .pdf)..."
	python3 scripts/generate_docx.py
	python3 scripts/generate_pdf.py
	python3 scripts/generate_pdf.py --input docs/USER_GUIDE.md

build:
	@echo "[build] Running PyInstaller..."
	pyinstaller droidbridge-gui.spec \
	    --distpath dist \
	    --workpath build/pyinstaller \
	    --noconfirm

package:
	@echo "[package] Packaging Linux release v$(VERSION)..."
	VERSION=$(VERSION) bash scripts/package-linux.sh

clean:
	@echo "[clean] Removing build artefacts..."
	rm -rf build/pyinstaller dist/droidbridge-linux
	@echo "Done. releases/ and docs/ are untouched."
