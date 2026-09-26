#!/usr/bin/env bash
set -Eeuo pipefail

APP_NAME="MediaTidy"
ARCH="x86_64"

# Lo script vive nella directory AppImage/, quindi il progetto è la directory superiore.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

BUILD_DIR="${ROOT_DIR}/build"
DIST_DIR="${ROOT_DIR}/dist"
APPDIR="${BUILD_DIR}/${APP_NAME}.AppDir"

ICON_SOURCE="${ROOT_DIR}/MT_Icon.png"
DESKTOP_SOURCE="${ROOT_DIR}/AppImage/${APP_NAME}.desktop"

TOOLS_DIR="${ROOT_DIR}/tools"
APPIMAGETOOL="${TOOLS_DIR}/appimagetool-${ARCH}.AppImage"

cd "${ROOT_DIR}"

if [[ ! -f "${ROOT_DIR}/media_tidy.py" ]]; then
    echo "Errore: file di avvio non trovato: ${ROOT_DIR}/media_tidy.py"
    exit 1
fi

if [[ ! -f "${ICON_SOURCE}" ]]; then
    echo "Errore: icona non trovata: ${ICON_SOURCE}"
    exit 1
fi

if [[ ! -f "${DESKTOP_SOURCE}" ]]; then
    echo "Errore: file desktop non trovato: ${DESKTOP_SOURCE}"
    exit 1
fi

if [[ ! -d "${ROOT_DIR}/venv" ]]; then
    echo "Errore: ambiente virtuale non trovato: ${ROOT_DIR}/venv"
    echo "Crealo con: python3 -m venv venv"
    exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
    echo "Errore: curl non è installato."
    echo "Installa curl con: sudo apt install curl"
    exit 1
fi

mkdir -p "${TOOLS_DIR}"

if [[ ! -f "${APPIMAGETOOL}" ]]; then
    echo "==> Scarico appimagetool..."
    curl -fL \
        -o "${APPIMAGETOOL}" \
        "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${ARCH}.AppImage"
fi

chmod +x "${APPIMAGETOOL}"

source "${ROOT_DIR}/venv/bin/activate"

rm -rf "${BUILD_DIR}" "${DIST_DIR}" "${ROOT_DIR}/${APP_NAME}.spec"

echo "==> Aggiorno pip..."
python -m pip install --upgrade pip wheel

echo "==> Installo dipendenze e PyInstaller..."
pip install -r "${ROOT_DIR}/requirements.txt"
pip install pyinstaller

echo "==> Creo bundle PyInstaller..."
pyinstaller \
    --noconfirm \
    --clean \
    --name "${APP_NAME}" \
    --onedir \
    --windowed \
    --paths "${ROOT_DIR}" \
    --paths "${ROOT_DIR}/core" \
    --paths "${ROOT_DIR}/ui" \
    --add-data "${ICON_SOURCE}:." \
    --collect-all qtpy \
    --collect-all requests \
    "${ROOT_DIR}/media_tidy.py"

echo "==> Preparo AppDir..."
mkdir -p "${APPDIR}/usr/bin"

cp -a "${DIST_DIR}/${APP_NAME}" "${APPDIR}/usr/bin/${APP_NAME}"

cat > "${APPDIR}/AppRun" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail

APPDIR="$(cd "$(dirname "$0")" && pwd)"
exec "${APPDIR}/usr/bin/MediaTidy/MediaTidy" "$@"
EOF

chmod +x "${APPDIR}/AppRun"

cp "${DESKTOP_SOURCE}" "${APPDIR}/${APP_NAME}.desktop"
cp "${ICON_SOURCE}" "${APPDIR}/${APP_NAME}.png"
ln -sf "${APP_NAME}.png" "${APPDIR}/.DirIcon"

echo "==> Creo AppImage..."
ARCH="${ARCH}" "${APPIMAGETOOL}" "${APPDIR}" \
    "${DIST_DIR}/${APP_NAME}-${ARCH}.AppImage"

chmod +x "${DIST_DIR}/${APP_NAME}-${ARCH}.AppImage"

echo
echo "========================================"
echo "AppImage creata con successo:"
echo "${DIST_DIR}/${APP_NAME}-${ARCH}.AppImage"
echo "========================================"
