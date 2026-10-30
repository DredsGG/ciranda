"""Textos do Ciranda em português, inglês e espanhol (regra 13).

t("chave", nome=valor) devolve o texto no idioma atual. Texto novo entra aqui já nos três.
Idioma: o escolhido no seletor PT · EN · ES (config "idioma"); se nunca escolheu, o do
Windows (pt-*, es-*; qualquer outro vira inglês).
"""

from __future__ import annotations

import os
import sys

IDIOMAS = ("pt", "en", "es")
NOMES = {"pt": "PT", "en": "EN", "es": "ES"}
_atual = ""  # definido por iniciar(); antes disso, o do sistema

# chave: (português, inglês, espanhol)
T = {
    # ---------- barra ----------
    "nada_tocando": ("Nada tocando", "Nothing playing", "Nada en reproducción"),
    "arraste_para_janela": ("Arraste pastas para a janela", "Drag folders into the window",
                            "Arrastra carpetas a la ventana"),
    "mostrar_na_fila": ("Mostrar na fila", "Show in the queue", "Mostrar en la cola"),
    "dica_anterior": ("Anterior (P)", "Previous (P)", "Anterior (P)"),
    "dica_play": ("Tocar / pausar (Espaço)", "Play / pause (Space)", "Reproducir / pausar (Espacio)"),
    "dica_proximo": ("Próximo (N)", "Next (N)", "Siguiente (N)"),
    "dica_aleatorio": ("Aleatório (S)", "Shuffle (S)", "Aleatorio (S)"),
    "dica_total": ("Clique: tempo total / tempo que falta", "Click: total time / time left",
                   "Clic: tiempo total / tiempo restante"),
    "dica_mudo": ("Mudo (M)", "Mute (M)", "Silenciar (M)"),
    "dica_pastas": ("Pastas: abrir, juntar, limpar (Ctrl+O abre direto)",
                    "Folders: open, add, clear (Ctrl+O opens directly)",
                    "Carpetas: abrir, añadir, limpiar (Ctrl+O abre directamente)"),
    "dica_fila": ("Fila (L)", "Queue (L)", "Cola (L)"),
    "dica_tela_cheia": ("Tela cheia (F / duplo clique)", "Full screen (F / double-click)",
                        "Pantalla completa (F / doble clic)"),
    "dica_repetir_nao": ("Repetir: desligado (R)", "Repeat: off (R)", "Repetir: desactivado (R)"),
    "dica_repetir_tudo": ("Repetir: a fila toda (R)", "Repeat: whole queue (R)", "Repetir: toda la cola (R)"),
    "dica_repetir_um": ("Repetir: só este (R)", "Repeat: this one (R)", "Repetir: solo este (R)"),
    "n_de_total": ("{n} de {total}", "{n} of {total}", "{n} de {total}"),
    "convertendo_heic": (" · convertendo HEIC…", " · converting HEIC…", " · convirtiendo HEIC…"),

    # ---------- tempo da foto ----------
    "dica_tempo_foto": ("Tempo de cada foto na tela antes de passar para a próxima.\n"
                        "Vídeo sempre toca até o fim. Atalho: + e −",
                        "How long each photo stays on screen before the next one.\n"
                        "Videos always play to the end. Shortcut: + and −",
                        "Cuánto tiempo queda cada foto en pantalla antes de pasar a la siguiente.\n"
                        "Los videos siempre se reproducen hasta el final. Atajo: + y −"),
    "foto_rotulo": ("Foto: {tempo}", "Photo: {tempo}", "Foto: {tempo}"),
    "tempo_de_cada_foto": ("Tempo de cada foto", "Time per photo", "Tiempo por foto"),
    "video_nao_usa": ("Vídeo não usa: sempre toca até o fim", "Not for videos: they always play to the end",
                      "No se aplica a los videos: siempre se reproducen hasta el final"),
    "outro_tempo": ("Outro tempo…", "Other time…", "Otro tiempo…"),
    "outro_tempo_agora": ("Outro tempo… (agora {tempo})", "Other time… (now {tempo})",
                          "Otro tiempo… (ahora {tempo})"),
    "segundos": ("Segundos:", "Seconds:", "Segundos:"),

    # ---------- tela inicial ----------
    "arraste_aqui": ("Arraste pastas aqui", "Drop folders here", "Suelta carpetas aquí"),
    "solte_para_tocar": ("Solte para tocar", "Drop to play", "Suelta para reproducir"),
    "vazio_sub": ("Fotos e vídeos da pasta e de todas as subpastas entram numa fila só.\n"
                  "Segure Ctrl ao soltar para juntar à fila atual.",
                  "Photos and videos from the folder and every subfolder go into one queue.\n"
                  "Hold Ctrl while dropping to add them to the current queue.",
                  "Las fotos y videos de la carpeta y de todas sus subcarpetas forman una sola cola.\n"
                  "Mantén Ctrl al soltar para sumarlos a la cola actual."),
    "abrir_pasta": ("Abrir pasta", "Open folder", "Abrir carpeta"),
    "continuar_ultima": ("Continuar a última fila ({nomes})", "Continue the last queue ({nomes})",
                         "Continuar la última cola ({nomes})"),
    "n_pastas": ("{n} pastas", "{n} folders", "{n} carpetas"),

    # ---------- rodapé ----------
    "relatar_bug": ("Relatar bug", "Report a bug", "Reportar un error"),
    "procurar_atualizacao": ("Procurar atualização", "Check for updates", "Buscar actualizaciones"),
    "feito_por": ("feito por", "made by", "hecho por"),
    "como_usar": ("Como usar", "How to use", "Cómo usar"),
    "idioma": ("Idioma", "Language", "Idioma"),

    # ---------- menus ----------
    "m_abrir": ("Abrir", "Open", "Abrir"),
    "abrir_pasta_desc": ("Toca a pasta e todas as subpastas (troca a fila)",
                         "Plays the folder and every subfolder (replaces the queue)",
                         "Reproduce la carpeta y todas sus subcarpetas (reemplaza la cola)"),
    "juntar_outra": ("Juntar outra pasta", "Add another folder", "Añadir otra carpeta"),
    "juntar_desc": ("Soma mais uma pasta à fila, sem parar o que toca",
                    "Adds one more folder to the queue without stopping playback",
                    "Suma una carpeta más a la cola sin detener lo que se reproduce"),
    "abrir_arquivos": ("Abrir arquivos", "Open files", "Abrir archivos"),
    "abrir_arquivos_desc": ("Escolher fotos ou vídeos soltos", "Pick individual photos or videos",
                            "Elegir fotos o videos sueltos"),
    "ultima_fila": ("Última fila", "Last queue", "Última cola"),
    "continuar_1": ("Continuar ({n} pasta)", "Continue ({n} folder)", "Continuar ({n} carpeta)"),
    "continuar_n": ("Continuar ({n} pastas)", "Continue ({n} folders)", "Continuar ({n} carpetas)"),
    "e_mais": (" e mais {n}", " and {n} more", " y {n} más"),
    "arquivo_na_tela": ("Arquivo na tela", "File on screen", "Archivo en pantalla"),
    "mostrar_explorer": ("Mostrar no Explorer", "Show in Explorer", "Mostrar en el Explorador"),
    "mostrar_explorer_desc": ("Abre a pasta onde ele está", "Opens the folder it's in",
                              "Abre la carpeta donde está"),
    "limpar": ("Limpar", "Clear", "Limpiar"),
    "limpar_fila": ("Limpar fila", "Clear queue", "Vaciar la cola"),
    "limpar_fila_desc": ("Esvazia a fila. O Continuar fica guardado", "Empties the queue. Continue is kept",
                         "Vacía la cola. Continuar se conserva"),
    "limpar_tudo": ("Limpar tudo", "Clear all", "Limpiar todo"),
    "limpar_tudo_desc": ("Fila e a lista do Continuar. Não apaga nada do PC",
                         "The queue and the Continue list. Nothing on your PC is deleted",
                         "La cola y la lista de Continuar. No se borra nada del PC"),
    "usar_padrao": ("Usar como app padrão…", "Use as default app…", "Usar como aplicación predeterminada…"),
    "usar_padrao_desc": ("Abre a tela do Windows para escolher o Ciranda para fotos e vídeos",
                         "Opens the Windows screen to choose Ciranda for photos and videos",
                         "Abre la pantalla de Windows para elegir Ciranda para fotos y videos"),
    "procurar_desc": ("Você está na v{versao}. Confere se saiu versão nova no GitHub "
                      "(o Ciranda também confere sozinho ao abrir)",
                      "You have v{versao}. Checks GitHub for a new version "
                      "(Ciranda also checks by itself when it opens)",
                      "Tienes la v{versao}. Busca una versión nueva en GitHub "
                      "(Ciranda también lo hace solo al abrirse)"),
    "relatar_bug_desc": ("Abre o relato no GitHub já preenchido, sem nomes de pastas e arquivos",
                         "Opens a prefilled report on GitHub, without folder or file names",
                         "Abre el informe en GitHub ya completado, sin nombres de carpetas ni archivos"),
    "como_usar_desc": ("Mostra o tutorial de novo", "Shows the tutorial again", "Muestra el tutorial otra vez"),
    "restaurar": ("Restaurar de fábrica…", "Factory reset…", "Restablecer de fábrica…"),
    "restaurar_desc": ("Volta todos os ajustes ao padrão e limpa fila, Continuar e cache. Não apaga nada do PC",
                       "Resets all settings and clears the queue, Continue and cache. Nothing on your PC is deleted",
                       "Restablece todos los ajustes y limpia la cola, Continuar y la caché. "
                       "No se borra nada del PC"),
    "m_pastas": ("Pastas", "Folders", "Carpetas"),
    "juntar_desc_curta": ("Soma à fila sem parar o que toca", "Adds to the queue without stopping",
                          "Suma a la cola sin detener"),
    "abrir_desc_curta": ("Troca a fila", "Replaces the queue", "Reemplaza la cola"),
    "tocar": ("Tocar", "Play", "Reproducir"),
    "tecla_espaco": ("Espaço", "Space", "Espacio"),
    "pausar": ("Pausar", "Pause", "Pausar"),
    "proximo": ("Próximo", "Next", "Siguiente"),
    "aleatorio_ligado": ("Aleatório: ligado", "Shuffle: on", "Aleatorio: activado"),
    "aleatorio_desligado": ("Aleatório: desligado", "Shuffle: off", "Aleatorio: desactivado"),
    "repetir_nao": ("Repetir: desligado", "Repeat: off", "Repetir: desactivado"),
    "repetir_tudo": ("Repetir: a fila toda", "Repeat: whole queue", "Repetir: toda la cola"),
    "repetir_um": ("Repetir: só este", "Repeat: this one", "Repetir: solo este"),
    "tela_cheia": ("Tela cheia", "Full screen", "Pantalla completa"),
    "sair_tela_cheia": ("Sair da tela cheia", "Exit full screen", "Salir de pantalla completa"),
    "tocar_agora": ("Tocar agora", "Play now", "Reproducir ahora"),
    "copiar_caminho": ("Copiar caminho", "Copy path", "Copiar ruta"),
    "tirar_da_fila": ("Tirar da fila", "Remove from queue", "Quitar de la cola"),
    "tirar_n_da_fila": ("Tirar {n} da fila", "Remove {n} from queue", "Quitar {n} de la cola"),

    # ---------- fila ----------
    "fila": ("Fila", "Queue", "Cola"),
    "pil_abrir": ("Abrir", "Open", "Abrir"),
    "pil_abrir_dica": ("Abrir pasta: troca a fila (Ctrl+O)", "Open folder: replaces the queue (Ctrl+O)",
                       "Abrir carpeta: reemplaza la cola (Ctrl+O)"),
    "pil_juntar": ("Juntar pasta", "Add folder", "Añadir"),  # espanhol curto: cabe na fila
    "pil_juntar_dica": ("Soma mais uma pasta à fila, sem parar o que toca (Ctrl+Shift+O)",
                        "Adds one more folder to the queue without stopping playback (Ctrl+Shift+O)",
                        "Suma una carpeta más a la cola sin detener lo que se reproduce (Ctrl+Shift+O)"),
    "pil_limpar_dica": ("Limpar fila ou limpar tudo", "Clear the queue or clear all", "Vaciar la cola o limpiar todo"),
    "filtro_tudo": ("Tudo", "All", "Todo"),
    "filtro_fotos": ("Fotos", "Photos", "Fotos"),
    "filtro_videos": ("Vídeos", "Videos", "Videos"),
    "filtro_tudo_dica": ("Fotos e vídeos (1)", "Photos and videos (1)", "Fotos y videos (1)"),
    "filtro_fotos_dica": ("Só fotos (2)", "Photos only (2)", "Solo fotos (2)"),
    "filtro_videos_dica": ("Só vídeos (3)", "Videos only (3)", "Solo videos (3)"),
    "buscar_fila": ("Buscar na fila (nome ou pasta)", "Search the queue (name or folder)",
                    "Buscar en la cola (nombre o carpeta)"),
    "resumo": ("{fila} na fila · {fotos} fotos · {videos} vídeos", "{fila} in queue · {fotos} photos · {videos} videos",
               "{fila} en la cola · {fotos} fotos · {videos} videos"),
    "resumo_pastas_1": ("de {pastas} pastas com mídia ({abertas} aberta, {lidas} lidas)",
                        "from {pastas} folders with media ({abertas} opened, {lidas} read)",
                        "de {pastas} carpetas con contenido ({abertas} abierta, {lidas} leídas)"),
    "resumo_pastas_n": ("de {pastas} pastas com mídia ({abertas} abertas, {lidas} lidas)",
                        "from {pastas} folders with media ({abertas} opened, {lidas} read)",
                        "de {pastas} carpetas con contenido ({abertas} abiertas, {lidas} leídas)"),
    "outros_tipos": (" · {n} arquivos de outros tipos", " · {n} files of other types", " · {n} archivos de otros tipos"),
    "um_nao_abriu": (" · 1 não abriu", " · 1 didn't open", " · 1 no se abrió"),
    "n_nao_abriram": (" · {n} não abriram", " · {n} didn't open", " · {n} no se abrieron"),
    "fila_vazia": ("Fila vazia. Arraste pastas para a janela.", "The queue is empty. Drag folders into the window.",
                   "La cola está vacía. Arrastra carpetas a la ventana."),
    "nao_abriu_pasta": ("não abriu · ", "didn't open · ", "no se abrió · "),

    # ---------- avisos e estados ----------
    "dlg_adicionar_pasta": ("Adicionar pasta à fila", "Add folder to the queue", "Añadir carpeta a la cola"),
    "dlg_abrir_arquivos": ("Abrir fotos e vídeos", "Open photos and videos", "Abrir fotos y videos"),
    "lendo": ("Lendo {nome}…", "Reading {nome}…", "Leyendo {nome}…"),
    "lendo_n": ("Lendo… {n} arquivos", "Reading… {n} files", "Leyendo… {n} archivos"),
    "nenhuma_midia": ("Nenhuma foto ou vídeo nessa pasta nem nas subpastas.",
                      "No photos or videos in that folder or its subfolders.",
                      "No hay fotos ni videos en esa carpeta ni en sus subcarpetas."),
    "limpar_tudo_confirma": ("Limpar a fila e a lista do \"Continuar\"?\n\nNenhuma foto ou vídeo do PC é apagado.",
                             "Clear the queue and the \"Continue\" list?\n\nNo photo or video on your PC is deleted.",
                             "¿Limpiar la cola y la lista de \"Continuar\"?\n\nNo se borra ninguna foto ni video del PC."),
    "limpos": ("Fila e Continuar limpos. Arraste pastas para começar.",
               "Queue and Continue cleared. Drag folders to start.",
               "Cola y Continuar limpios. Arrastra carpetas para empezar."),
    "restaurar_titulo": ("Restaurar de fábrica", "Factory reset", "Restablecer de fábrica"),
    "restaurar_confirma": ("Voltar o Ciranda ao estado de recém-instalado?\n\n"
                           "• Ajustes voltam ao padrão (volume, aleatório, repetir, tempo da foto, filtro, janela)\n"
                           "• Fila, Continuar e cache das fotos HEIC são limpos\n\n"
                           "Nenhuma foto ou vídeo do PC é apagado.",
                           "Put Ciranda back as if it was just installed?\n\n"
                           "• Settings go back to default (volume, shuffle, repeat, photo time, filter, window)\n"
                           "• The queue, Continue and the HEIC photo cache are cleared\n\n"
                           "No photo or video on your PC is deleted.",
                           "¿Dejar Ciranda como recién instalado?\n\n"
                           "• Los ajustes vuelven a los valores de fábrica (volumen, aleatorio, repetir, "
                           "tiempo por foto, filtro, ventana)\n"
                           "• Se limpian la cola, Continuar y la caché de fotos HEIC\n\n"
                           "No se borra ninguna foto ni video del PC."),
    "restaurado": ("Ciranda restaurado de fábrica. Arraste pastas para começar.",
                   "Ciranda was reset. Drag folders to start.",
                   "Ciranda restablecido de fábrica. Arrastra carpetas para empezar."),
    "fim_fila": ("Fim da fila. Aperte ▶ para começar de novo.", "End of the queue. Press ▶ to start again.",
                 "Fin de la cola. Pulsa ▶ para empezar de nuevo."),
    "nenhum_abriu": ("Nenhum arquivo da fila abriu.", "None of the files in the queue opened.",
                     "No se abrió ningún archivo de la cola."),
    "nada_com_filtro": ("Nada na fila com esse filtro.", "Nothing in the queue with this filter.",
                        "Nada en la cola con este filtro."),
    "osd_volume": ("Volume {v}%", "Volume {v}%", "Volumen {v}%"),
    "osd_sem_som": ("Sem som", "Sound off", "Sin sonido"),
    "osd_som": ("Som ligado", "Sound on", "Sonido activado"),
    "osd_aleatorio": ("Aleatório ligado", "Shuffle on", "Aleatorio activado"),
    "osd_em_ordem": ("Em ordem", "In order", "En orden"),
    "osd_repetir_nao": ("Repetir desligado", "Repeat off", "Repetir desactivado"),
    "osd_repetir_tudo": ("Repetir a fila toda", "Repeat the whole queue", "Repetir toda la cola"),
    "osd_repetir_um": ("Repetir só este", "Repeat this one", "Repetir solo este"),
    "osd_filtro_tudo": ("Mostrando fotos e vídeos", "Showing photos and videos", "Mostrando fotos y videos"),
    "osd_filtro_fotos": ("Só fotos", "Photos only", "Solo fotos"),
    "osd_filtro_videos": ("Só vídeos", "Videos only", "Solo videos"),
    "osd_cada_foto": ("Cada foto: {v} s", "Each photo: {v} s", "Cada foto: {v} s"),
    "nao_abriu_app": ("O Ciranda não conseguiu abrir.\nDetalhes em %APPDATA%\\Ciranda\\erro.txt",
                      "Ciranda couldn't open.\nDetails in %APPDATA%\\Ciranda\\erro.txt",
                      "Ciranda no pudo abrirse.\nDetalles en %APPDATA%\\Ciranda\\erro.txt"),

    # ---------- atualização ----------
    "ver_e_atualizar": ("Ver e atualizar", "View and update", "Ver y actualizar"),
    "depois": ("Depois", "Later", "Después"),
    "procurando": ("Procurando atualização…", "Checking for updates…", "Buscando actualizaciones…"),
    "sem_github": ("Não consegui falar com o GitHub agora (sem internet?).\nTente de novo daqui a pouco.",
                   "Couldn't reach GitHub right now (no internet?).\nTry again in a moment.",
                   "No pude conectar con GitHub ahora (¿sin internet?).\nInténtalo de nuevo en un momento."),
    "ja_mais_nova": ("Você já está na versão mais nova (v{versao}).", "You already have the latest version (v{versao}).",
                     "Ya tienes la versión más reciente (v{versao})."),
    "faixa_nova": ("<b>Ciranda v{versao}</b> disponível", "<b>Ciranda v{versao}</b> is available",
                   "<b>Ciranda v{versao}</b> disponible"),
    "faixa_teste": ("<b>Ciranda v{versao} (teste)</b> pronto para instalar", "<b>Ciranda v{versao} (test)</b> ready to install",
                    "<b>Ciranda v{versao} (prueba)</b> lista para instalar"),
    "voce_esta_na": ("você está na v{versao}", "you have v{versao}", "tienes la v{versao}"),
    "da_pasta_teste": ("da sua pasta de teste", "from your test folder", "de tu carpeta de prueba"),
    "nova_versao": ("Nova versão v{versao}", "New version v{versao}", "Nueva versión v{versao}"),
    "nova_versao_teste": ("Nova versão v{versao} (teste)", "New version v{versao} (test)",
                          "Nueva versión v{versao} (prueba)"),
    "atualizar": ("Atualizar", "Update", "Actualizar"),
    "nova_versao_urgente": ("Atualização urgente v{versao}", "Urgent update v{versao}", "Actualización urgente v{versao}"),
    "urgente_explica": ("Esta versão corrige um problema grave. O Ciranda fica pausado até você atualizar.",
                        "This version fixes a serious problem. Ciranda stays paused until you update.",
                        "Esta versión corrige un problema grave. Ciranda queda en pausa hasta que actualices."),
    "pronta_titulo": ("Ciranda v{versao} baixada", "Ciranda v{versao} downloaded", "Ciranda v{versao} descargada"),
    "pronta_corpo": ("Instala sozinha quando este arquivo terminar, quando você pausar ou ao fechar o Ciranda, "
                     "e ele volta de onde parou.",
                     "It installs by itself when this file ends, when you pause or when you close Ciranda, "
                     "and it picks up where you left off.",
                     "Se instala sola cuando termine este archivo, cuando pauses o al cerrar Ciranda, "
                     "y vuelve a donde lo dejaste."),
    "atualizando_ja": ("Atualizando para a v{versao}… volta já de onde parou",
                       "Updating to v{versao}… back where you left off in a moment",
                       "Actualizando a la v{versao}… enseguida vuelve a donde lo dejaste"),
    # Apoiar ♥ (regra 16): doação opcional
    "apoiar": ("Apoiar ♥", "Support ♥", "Apoyar ♥"),
    "apoio_onde": ("De onde você é?", "Where are you from?", "¿De dónde eres?"),
    "apoio_brasil": ("Brasil", "Brazil", "Brasil"),
    "apoio_brasil_sub": ("Pix, em reais, na hora", "Pix, in reais, instantly", "Pix, en reales, al instante"),
    "apoio_fora": ("Outro país", "Another country", "Otro país"),
    "apoio_fora_sub": ("Cartão, em dólar, pelo GitHub Sponsors", "Card, in dollars, via GitHub Sponsors",
                       "Tarjeta, en dólares, por GitHub Sponsors"),
    "apoio_opcional": ("É opcional e não muda nada no Ciranda. Obrigado por usar!",
                       "It's optional and changes nothing in Ciranda. Thanks for using it!",
                       "Es opcional y no cambia nada en Ciranda. ¡Gracias por usarlo!"),
    "apoio_pix_titulo": ("Apoiar com Pix", "Support with Pix", "Apoyar con Pix"),
    "apoio_outro_valor": ("Outro valor", "Other amount", "Otro valor"),
    "apoio_valor_dica": ("Em reais, de R$ 1 a R$ 10.000. Vazio: você digita o valor no banco.",
                         "In reais, from R$ 1 to R$ 10,000. Empty: you type the amount in your bank app.",
                         "En reales, de R$ 1 a R$ 10.000. Vacío: escribes el valor en tu banco."),
    "apoio_valor_ruim": ("Valor de R$ 1 a R$ 10.000.", "Amount from R$ 1 to R$ 10,000.", "Valor de R$ 1 a R$ 10.000."),
    "apoio_valor_livre": ("valor livre", "any amount", "valor libre"),
    "apoio_qr_alt": ("QR Code Pix de {valor}", "Pix QR Code for {valor}", "Código QR Pix de {valor}"),
    "apoio_sem_qr": ("Não deu para desenhar o QR aqui. Use o Copiar código Pix abaixo.",
                     "Couldn't draw the QR here. Use Copy Pix code below.",
                     "No se pudo dibujar el QR aquí. Usa Copiar código Pix abajo."),
    "apoio_copiar_codigo": ("Copiar código Pix", "Copy Pix code", "Copiar código Pix"),
    "apoio_copiado": ("Copiado!", "Copied!", "¡Copiado!"),
    "apoio_chave": ("Chave", "Key", "Clave"),
    "apoio_copiar_chave": ("Copiar chave", "Copy key", "Copiar clave"),
    "apoio_instrucoes": ("Abra o app do seu banco, escolha Pix → Ler QR Code ou Pix Copia e Cola. "
                         "O nome que aparece é Andre Miller Fleck.",
                         "Open your bank app, choose Pix → Scan QR Code or Pix Copy and Paste. "
                         "The name shown is Andre Miller Fleck.",
                         "Abre la app de tu banco, elige Pix → Leer código QR o Pix Copia y Pega. "
                         "El nombre que aparece es Andre Miller Fleck."),
    "apoio_fora_titulo": ("Apoiar pelo GitHub Sponsors", "Support on GitHub Sponsors", "Apoyar en GitHub Sponsors"),
    "apoio_fora_texto": ("Uma vez ou todo mês, a partir de US$ 1. Pagamento com cartão pelo GitHub, sem taxa para mim.",
                         "One-time or monthly, from US$ 1. Card payments through GitHub, no fee for me.",
                         "Una vez o cada mes, desde US$ 1. Pago con tarjeta por GitHub, sin comisión para mí."),
    "apoio_abrir_sponsors": ("Abrir GitHub Sponsors", "Open GitHub Sponsors", "Abrir GitHub Sponsors"),
    "apoio_voltar": ("← Voltar", "← Back", "← Volver"),
    "dlg_atualizacao": ("Atualização do Ciranda", "Ciranda update", "Actualización de Ciranda"),
    "disponivel": ("Ciranda v{versao} disponível", "Ciranda v{versao} is available", "Ciranda v{versao} disponible"),
    "disponivel_teste": ("Ciranda v{versao} (teste) disponível", "Ciranda v{versao} (test) is available",
                         "Ciranda v{versao} (prueba) disponible"),
    "voce_esta_na_frase": ("Você está na v{versao}.", "You have v{versao}.", "Tienes la v{versao}."),
    "veio_pasta_teste": (" Esta versão veio da sua pasta de teste e ainda não está no GitHub.",
                         " This build came from your test folder and isn't on GitHub yet.",
                         " Esta versión viene de tu carpeta de prueba y aún no está en GitHub."),
    "o_que_mudou": ("O que mudou", "What changed", "Qué cambió"),
    "ver_tudo_github": ("Ver tudo no GitHub", "See everything on GitHub", "Ver todo en GitHub"),
    "atualizar_agora": ("Atualizar agora", "Update now", "Actualizar ahora"),
    "baixar_github": ("Baixar no GitHub", "Download from GitHub", "Descargar de GitHub"),
    "dica_instala": ("O Ciranda fecha, instala sozinho e abre de novo de onde parou. Seus ajustes ficam.",
                     "Ciranda closes, installs by itself and opens again where you left off. Your settings stay.",
                     "Ciranda se cierra, se instala solo y vuelve a abrirse donde lo dejaste. Tus ajustes se mantienen."),
    "dica_zip": ("Este Ciranda não veio do instalador: baixe a versão nova na página.",
                 "This Ciranda wasn't installed with the setup: download the new version from the page.",
                 "Este Ciranda no se instaló con el instalador: descarga la versión nueva en la página."),
    "cancelar": ("Cancelar", "Cancel", "Cancelar"),
    "copiando": ("Copiando…", "Copying…", "Copiando…"),
    "baixando": ("Baixando…", "Downloading…", "Descargando…"),
    "copiando_mb": ("Copiando… {feito} de {total} MB", "Copying… {feito} of {total} MB", "Copiando… {feito} de {total} MB"),
    "baixando_mb": ("Baixando… {feito} de {total} MB", "Downloading… {feito} of {total} MB",
                    "Descargando… {feito} de {total} MB"),
    "instalando": ("Instalando…", "Installing…", "Instalando…"),
    "conferido_instalando": ("Conferido (SHA-256 igual ao do GitHub). Instalando…",
                             "Verified (SHA-256 matches GitHub). Installing…",
                             "Verificado (SHA-256 igual al de GitHub). Instalando…"),
    "erro_abrir_instalador": ("não consegui abrir o instalador ({erro})", "couldn't start the installer ({erro})",
                              "no pude abrir el instalador ({erro})"),
    "tentar_de_novo": ("Tentar de novo", "Try again", "Intentar de nuevo"),
    "download_cancelado": ("Download cancelado.", "Download canceled.", "Descarga cancelada."),
    "nao_deu_atualizar": ("Não deu para atualizar: {msg}. Tente de novo ou baixe na página.",
                          "Couldn't update: {msg}. Try again or download it from the page.",
                          "No se pudo actualizar: {msg}. Inténtalo de nuevo o descárgalo en la página."),
    "erro_endereco": ("endereço do instalador fora do repositório do Ciranda",
                      "the installer link is outside Ciranda's repository",
                      "el enlace del instalador está fuera del repositorio de Ciranda"),
    "erro_sem_sha": ("o GitHub não informou o SHA-256 do instalador", "GitHub didn't provide the installer's SHA-256",
                     "GitHub no informó el SHA-256 del instalador"),
    "erro_sha": ("o instalador baixado não confere com o SHA-256 do GitHub",
                 "the downloaded installer doesn't match GitHub's SHA-256",
                 "el instalador descargado no coincide con el SHA-256 de GitHub"),
    "erro_local": ("o instalador da pasta de teste está incompleto ou não confere com o .sha256",
                   "the installer in the test folder is incomplete or doesn't match its .sha256",
                   "el instalador de la carpeta de prueba está incompleto o no coincide con su .sha256"),
    "notas_teste": ("Versão de teste: ainda não publicada no GitHub.", "Test build: not published on GitHub yet.",
                    "Versión de prueba: aún no publicada en GitHub."),

    # ---------- novidades e tutorial ----------
    "novidades_da": ("Novidades da v{versao}", "What's new in v{versao}", "Novedades de la v{versao}"),
    "atualizado_de": ("O Ciranda foi atualizado da v{antes} para a v{agora}.",
                      "Ciranda was updated from v{antes} to v{agora}.",
                      "Ciranda se actualizó de la v{antes} a la v{agora}."),
    "reinstalado": ("O Ciranda foi reinstalado na v{agora} (versão de teste nova).",
                    "Ciranda was reinstalled at v{agora} (new test build).",
                    "Ciranda se reinstaló en la v{agora} (nueva versión de prueba)."),
    "entendi": ("Entendi", "Got it", "Entendido"),
    "pular": ("Pular", "Skip", "Omitir"),
    "voltar": ("Voltar", "Back", "Atrás"),
    "passo_n": ("{n} de {total}", "{n} of {total}", "{n} de {total}"),
    "fechar_esc": ("Fechar (Esc)", "Close (Esc)", "Cerrar (Esc)"),
    "tut1_t": ("Bem-vindo ao Ciranda", "Welcome to Ciranda", "Te damos la bienvenida a Ciranda"),
    "tut1": ("Arraste uma pasta para a janela (ou use Abrir pasta): as fotos e vídeos dela e de todas as "
             "subpastas viram uma fila só.",
             "Drag a folder into the window (or use Open folder): its photos and videos, and those of every "
             "subfolder, become one queue.",
             "Arrastra una carpeta a la ventana (o usa Abrir carpeta): sus fotos y videos, y los de todas sus "
             "subcarpetas, forman una sola cola."),
    "tut2_t": ("Tocar do seu jeito", "Play it your way", "A tu manera"),
    "tut2": ("Na barra de baixo: aleatório (S), anterior e próximo, repetir (R) e quanto tempo cada foto fica "
             "na tela. Vídeo sempre toca até o fim.",
             "On the bottom bar: shuffle (S), previous and next, repeat (R) and how long each photo stays on "
             "screen. Videos always play to the end.",
             "En la barra de abajo: aleatorio (S), anterior y siguiente, repetir (R) y cuánto tiempo queda cada "
             "foto en pantalla. Los videos siempre se reproducen hasta el final."),
    "tut3_t": ("A fila", "The queue", "La cola"),
    "tut3": ("À direita (L mostra e esconde): busque pelo nome, filtre fotos ou vídeos (1, 2, 3), dois cliques "
             "para tocar e botão direito para mostrar no Explorer ou tirar da fila.",
             "On the right (L shows and hides it): search by name, filter photos or videos (1, 2, 3), "
             "double-click to play and right-click to show in Explorer or remove.",
             "A la derecha (L la muestra y la oculta): busca por nombre, filtra fotos o videos (1, 2, 3), doble "
             "clic para reproducir y clic derecho para mostrar en el Explorador o quitar de la cola."),
    "tut4_t": ("O menu da pastinha", "The folder menu", "El menú de la carpeta"),
    "tut4": ("O ícone de pasta na barra junta outra pasta, continua a última fila, limpa e restaura de "
             "fábrica. Nada disso apaga arquivo do PC.",
             "The folder icon on the bar adds another folder, continues the last queue, clears and resets. "
             "None of it deletes files from your PC.",
             "El icono de carpeta en la barra añade otra carpeta, continúa la última cola, limpia y restablece. "
             "Nada de eso borra archivos del PC."),
    "tut5_t": ("Tela cheia e rodapé", "Full screen and footer", "Pantalla completa y pie"),
    "tut5": ("Dois cliques no vídeo (ou F) para tela cheia. Embaixo da fila: idioma (PT · EN · ES), Relatar "
             "bug, Procurar atualização e o ? para ver este tutorial de novo.",
             "Double-click the video (or F) for full screen. Below the queue: language (PT · EN · ES), Report a "
             "bug, Check for updates and the ? to see this tutorial again.",
             "Doble clic en el video (o F) para pantalla completa. Debajo de la cola: idioma (PT · EN · ES), "
             "Reportar un error, Buscar actualizaciones y el ? para ver este tutorial otra vez."),

    # ---------- relatar bug ----------
    "bug_pergunta": ("O que aconteceu? O que você estava fazendo?", "What happened? What were you doing?",
                     "¿Qué pasó? ¿Qué estabas haciendo?"),
    "bug_exemplo": ("Ex.: abri uma pasta com vídeos .mov e a tela ficou preta",
                    "E.g.: I opened a folder with .mov videos and the screen went black",
                    "Ej.: abrí una carpeta con videos .mov y la pantalla se puso negra"),
    "incluir_diag": ("Incluir diagnóstico (versões, ajustes, fim do log)",
                     "Include diagnostics (versions, settings, end of the log)",
                     "Incluir diagnóstico (versiones, ajustes, final del registro)"),
    "bug_aviso": ("Nomes de pastas, arquivos, do usuário e do PC são tirados: fica só a extensão. Nada é enviado "
                  "sozinho: o GitHub abre no navegador e você confere antes de enviar (precisa de conta no "
                  "GitHub; sem conta, use Copiar relatório).",
                  "Folder, file, user and PC names are removed: only the extension stays. Nothing is sent by "
                  "itself: GitHub opens in your browser and you check it before submitting (it needs a GitHub "
                  "account; without one, use Copy report).",
                  "Se quitan los nombres de carpetas, archivos, usuario y PC: solo queda la extensión. No se "
                  "envía nada solo: GitHub se abre en el navegador y lo revisas antes de enviar (necesita una "
                  "cuenta de GitHub; sin cuenta, usa Copiar informe)."),
    "copiar_relatorio": ("Copiar relatório", "Copy report", "Copiar informe"),
    "abrir_github": ("Abrir no GitHub", "Open on GitHub", "Abrir en GitHub"),
    "copiado": ("Copiado. Cole em github.com/DredsGG/ciranda/issues ou mande para o Dreds.",
                "Copied. Paste it at github.com/DredsGG/ciranda/issues or send it to Dreds.",
                "Copiado. Pégalo en github.com/DredsGG/ciranda/issues o envíalo a Dreds."),
    "abri_github": ("Abri o GitHub no navegador. Confira o texto e envie lá.",
                    "GitHub is open in your browser. Check the text and submit it there.",
                    "Abrí GitHub en el navegador. Revisa el texto y envíalo allí."),
    "log_grande": (" O log era grande: o relatório completo foi copiado (Ctrl+V para colar).",
                   " The log was long: the full report was copied (Ctrl+V to paste).",
                   " El registro era largo: el informe completo se copió (Ctrl+V para pegar)."),
    "diag_instalado": ("instalado", "installed", "instalado"),
    "diag_codigo": ("pelo código / zip", "from source / zip", "desde el código / zip"),
    "diag_sistema": ("Sistema", "System", "Sistema"),
    "diag_telas": ("Telas", "Screens", "Pantallas"),
    "diag_fila": ("Fila", "Queue", "Cola"),
    "diag_modos": ("Modos", "Modes", "Modos"),
    "diag_atual": ("Na tela", "On screen", "En pantalla"),
    "diag_ultimo_erro": ("Último erro (erro.txt):", "Last error (erro.txt):", "Último error (erro.txt):"),
    "diag_fim_log": ("Fim do log (ciranda.log):", "End of the log (ciranda.log):", "Final del registro (ciranda.log):"),
    "diag_fila_txt": ("{itens} itens ({fotos} fotos, {videos} vídeos), {abertas} pastas abertas, {lidas} pastas lidas, "
                      "{outros} arquivos de outros tipos",
                      "{itens} items ({fotos} photos, {videos} videos), {abertas} folders opened, {lidas} folders read, "
                      "{outros} files of other types",
                      "{itens} elementos ({fotos} fotos, {videos} videos), {abertas} carpetas abiertas, "
                      "{lidas} carpetas leídas, {outros} archivos de otros tipos"),
    "diag_modos_txt": ("aleatório {aleatorio}, repetir {repetir}, filtro {filtro}, foto {foto} s, volume {volume}{mudo}, "
                       "tela cheia {cheia}, idioma {idioma}",
                       "shuffle {aleatorio}, repeat {repetir}, filter {filtro}, photo {foto} s, volume {volume}{mudo}, "
                       "full screen {cheia}, language {idioma}",
                       "aleatorio {aleatorio}, repetir {repetir}, filtro {filtro}, foto {foto} s, volumen {volume}{mudo}, "
                       "pantalla completa {cheia}, idioma {idioma}"),
    "diag_mudo": (" (mudo)", " (muted)", " (silenciado)"),
    "diag_em": (" em {pos} de {total}", " at {pos} of {total}", " en {pos} de {total}"),
    "diag_falhou": (" (falhou)", " (failed)", " (falló)"),
    "sim": ("sim", "yes", "sí"),
    "nao": ("não", "no", "no"),
    "bug_o_que": ("### O que aconteceu", "### What happened", "### Qué pasó"),
    "bug_nao_escrito": ("_(não escrito)_", "_(not written)_", "_(sin escribir)_"),
    "bug_diag": ("### Diagnóstico", "### Diagnostics", "### Diagnóstico"),
    "bug_enviado": ("_Enviado pelo botão \"Relatar bug\" do Ciranda v{versao}._",
                    "_Sent with the \"Report a bug\" button in Ciranda v{versao}._",
                    "_Enviado con el botón \"Reportar un error\" de Ciranda v{versao}._"),
    "log_cortado": ("(começo cortado; o completo vai no \"Copiar relatório\")",
                    "(beginning cut; the full log is in \"Copy report\")",
                    "(inicio recortado; el completo va en \"Copiar informe\")"),
    "diag_grande": ("_(grande demais para o endereço: foi copiado; cole aqui com Ctrl+V)_",
                    "_(too long for the link: it was copied; paste it here with Ctrl+V)_",
                    "_(demasiado largo para el enlace: se copió; pégalo aquí con Ctrl+V)_"),
}


def normalizar(codigo: str) -> str:
    """pt-BR → pt, es-419 → es, en-US → en; qualquer outro → en."""
    c = (codigo or "").strip().lower().replace("_", "-")
    for i in IDIOMAS:
        if c == i or c.startswith(i + "-"):
            return i
    return "en"


def idioma_do_sistema() -> str:
    """Idioma da interface do Windows (GetUserPreferredUILanguages); no Linux, LANG / Qt."""
    forcado = os.environ.get("CIRANDA_IDIOMA_SISTEMA")  # testes: simula o sistema em outro idioma
    if forcado:
        return normalizar(forcado)
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
            k = ctypes.windll.kernel32
            n_idiomas, tam = wintypes.ULONG(0), wintypes.ULONG(0)
            MUI_LANGUAGE_NAME = 0x8
            if k.GetUserPreferredUILanguages(MUI_LANGUAGE_NAME, ctypes.byref(n_idiomas), None, ctypes.byref(tam)):
                buf = ctypes.create_unicode_buffer(tam.value)
                if k.GetUserPreferredUILanguages(MUI_LANGUAGE_NAME, ctypes.byref(n_idiomas), buf, ctypes.byref(tam)):
                    primeiro = buf[:tam.value].split("\x00")[0]
                    if primeiro:
                        return normalizar(primeiro)
        except Exception:
            pass
    try:
        from PySide6.QtCore import QLocale
        langs = QLocale.system().uiLanguages()
        if langs:
            return normalizar(langs[0])
    except Exception:
        pass
    return normalizar(os.environ.get("LANG", "en").split(".")[0])


def definir(idioma: str):
    global _atual
    _atual = idioma if idioma in IDIOMAS else "en"


def atual() -> str:
    if not _atual:
        definir(idioma_do_sistema())
    return _atual


def iniciar(cfg: dict) -> str:
    """Escolhe o idioma ao abrir: o salvo no seletor, senão o do sistema."""
    definir(cfg.get("idioma") if cfg.get("idioma") in IDIOMAS else idioma_do_sistema())
    return _atual


def t(chave: str, **kw) -> str:
    trio = T[chave]
    txt = trio[IDIOMAS.index(atual())] or trio[1]
    return txt.format(**kw) if kw else txt
