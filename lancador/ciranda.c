/* Ciranda.exe: abre o Ciranda com dois cliques.
 * - Ambiente já instalado: roda .venv\Scripts\pythonw.exe app.py <argumentos> (sem janela preta).
 * - Primeira vez: roda o RODAR.bat (instala Python/dependências e depois abre).
 * Os argumentos (pastas do "Abrir com" / botão direito) são repassados.
 * Feito por Dreds. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shlwapi.h>
#include <wchar.h>

static int existe(const wchar_t *p) {
    DWORD a = GetFileAttributesW(p);
    return a != INVALID_FILE_ATTRIBUTES && !(a & FILE_ATTRIBUTE_DIRECTORY);
}

static int rodar(wchar_t *linha, const wchar_t *pasta, DWORD flags, WORD mostrar) {
    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof si);
    si.cb = sizeof si;
    si.dwFlags = STARTF_USESHOWWINDOW;
    si.wShowWindow = mostrar;
    if (!CreateProcessW(NULL, linha, NULL, NULL, FALSE, flags, NULL, pasta, &si, &pi))
        return 0;
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    return 1;
}

int WINAPI wWinMain(HINSTANCE h, HINSTANCE p, PWSTR cmd, int show) {
    (void)h; (void)p; (void)cmd; (void)show;
    wchar_t pasta[MAX_PATH], pyw[MAX_PATH], pronto[MAX_PATH], app[MAX_PATH], bat[MAX_PATH];
    static wchar_t linha[32768];

    GetModuleFileNameW(NULL, pasta, MAX_PATH);
    PathRemoveFileSpecW(pasta);
    swprintf(pyw, MAX_PATH, L"%ls\\.venv\\Scripts\\pythonw.exe", pasta);
    swprintf(pronto, MAX_PATH, L"%ls\\.venv\\pronto-1.0.txt", pasta);
    swprintf(app, MAX_PATH, L"%ls\\app.py", pasta);
    swprintf(bat, MAX_PATH, L"%ls\\RODAR.bat", pasta);

    const wchar_t *args = PathGetArgsW(GetCommandLineW());
    if (!args) args = L"";

    if (existe(pyw) && existe(pronto)) {
        swprintf(linha, 32768, L"\"%ls\" \"%ls\" %ls", pyw, app, args);
        if (rodar(linha, pasta, 0, SW_SHOWNORMAL))
            return 0;
    }
    if (existe(bat)) {
        /* cmd /c ""bat" args": as aspas externas são do próprio cmd */
        swprintf(linha, 32768, L"cmd.exe /c \"\"%ls\" %ls\"", bat, args);
        if (rodar(linha, pasta, CREATE_NEW_CONSOLE, SW_SHOWNORMAL))
            return 0;
    }
    MessageBoxW(NULL,
                L"Não achei os arquivos do Ciranda ao lado deste Ciranda.exe.\n"
                L"Ele precisa ficar dentro da pasta do Ciranda (com app.py e RODAR.bat).",
                L"Ciranda", MB_ICONERROR);
    return 1;
}
