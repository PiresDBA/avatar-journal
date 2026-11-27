"""CLI uploader para publicar Shorts/vídeos no YouTube Data API v3 com verificação estrita de canal."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

DEFAULT_CLIENT_SECRETS = r"d:\Utilitarios\avatar-journal\tools\client_secret_AI.json"
DEFAULT_TOKEN = r"d:\Utilitarios\avatar-journal\tools\token_youtube.json"


def _norm_handle(value: str) -> str:
    return value.strip().lstrip("@").lower()


def _norm_title(value: str) -> str:
    return " ".join(value.strip().lower().split())


def authenticate(client_secrets: Path, token_path: Path) -> tuple[Credentials, bool]:
    """Carrega token válido/renováveis ou inicia OAuth InstalledAppFlow no navegador."""
    creds: Credentials | None = None
    refreshed_or_new = False

    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except Exception as exc:
            print(f"[AUTH] Token existente inválido ({exc}); iniciando novo OAuth.", flush=True)
            creds = None

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            refreshed_or_new = True
        except Exception as exc:
            print(f"[AUTH] Falha ao renovar token ({exc}); iniciando novo OAuth.", flush=True)
            creds = None

    if not creds or not creds.valid or not creds.has_scopes(SCOPES):
        if not client_secrets.exists():
            raise FileNotFoundError(f"Arquivo client_secrets não encontrado: {client_secrets}")
        print(
            "[OAUTH] Iniciando fluxo OAuth local — selecione o canal esperado no navegador...",
            flush=True,
        )
        flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets), SCOPES)
        creds = flow.run_local_server(
            port=0,
            open_browser=True,
            prompt="select_account consent",
            authorization_prompt_message=(
                "[OAUTH_URL] Abra este link no navegador e autorize o canal:\n{url}\n"
            ),
        )
        refreshed_or_new = True

    return creds, refreshed_or_new


def verify_channel(
    youtube,
    expected_handle: str,
    expected_channel: str,
    token_path: Path,
) -> dict[str, str]:
    """Confirma que a conta autenticada corresponde exatamente ao canal alvo."""
    resp = youtube.channels().list(part="snippet,statistics", mine=True).execute()
    items = resp.get("items") or []
    if not items:
        if token_path.exists():
            token_path.unlink(missing_ok=True)
        print("[ERROR] Nenhum canal YouTube encontrado para a conta autenticada.", flush=True)
        sys.exit(2)

    channel = items[0]
    snippet = channel.get("snippet") or {}
    channel_id = channel.get("id", "")
    title = snippet.get("title", "")
    custom_url = snippet.get("customUrl", "")

    print(
        f"[CHANNEL] id={channel_id} | title={title} | handle={custom_url or '(sem handle)'}",
        flush=True,
    )

    exp_h = _norm_handle(expected_handle)
    exp_t = _norm_title(expected_channel)
    got_h = _norm_handle(custom_url)
    got_t = _norm_title(title)

    matched = (got_h == exp_h) if got_h else (got_t == exp_t)
    if not matched:
        if token_path.exists():
            token_path.unlink(missing_ok=True)
        print(
            "[ERROR] Canal autenticado não confere com esperado! Abortando upload sem publicar.\n"
            f"        Esperado: title='{expected_channel}' / handle='{expected_handle}'\n"
            f"        Recebido: title='{title}' / handle='{custom_url}'",
            flush=True,
        )
        sys.exit(2)

    return {"id": channel_id, "title": title, "handle": custom_url}


def upload_video(
    youtube,
    video_path: Path,
    title: str,
    description: str,
    tags: list[str],
    category_id: str,
    privacy: str,
) -> dict:
    """Envia o vídeo MP4 via upload resumable com chunksize de 4 MiB."""
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id,
            "defaultLanguage": "pt-BR",
            "defaultAudioLanguage": "pt-BR",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        chunksize=4 * 1024 * 1024,
        resumable=True,
    )
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    last_pct = -1
    print(f"[UPLOAD] Iniciando upload de {video_path.name} ({video_path.stat().st_size} bytes)...", flush=True)
    while response is None:
        status, response = request.next_chunk()
        if status is not None:
            pct = int(status.progress() * 100)
            if pct != last_pct:
                print(f"[UPLOAD] Progresso: {pct}%", flush=True)
                last_pct = pct

    return response


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publica Short/vídeo no YouTube Data API v3")
    parser.add_argument("--video", required=True, help="Caminho do arquivo MP4")
    parser.add_argument("--title", required=True, help="Título do vídeo (<= 100 caracteres)")
    parser.add_argument("--description", required=True, help="Descrição do vídeo")
    parser.add_argument("--tags", default="", help="Tags separadas por vírgula")
    parser.add_argument(
        "--privacy",
        default="public",
        choices=["public", "unlisted", "private"],
        help="Privacidade desejada",
    )
    parser.add_argument("--category-id", default="28", help="ID da categoria YouTube (28=Science & Tech)")
    parser.add_argument("--client-secrets", default=DEFAULT_CLIENT_SECRETS)
    parser.add_argument("--token", default=DEFAULT_TOKEN)
    parser.add_argument("--expected-handle", default="@ai-Journal-4-all")
    parser.add_argument("--expected-channel", default="AI Journal 4 ALL")
    parser.add_argument("--dry-run", action="store_true", help="Somente autenticar e conferir canal")
    parser.add_argument("--record-history", action="store_true", help="Registra a publicacao em data/published_history.json")
    parser.add_argument("--topics-json", default="", help="JSON com lista de topicos para anti-repeticao")
    parser.add_argument("--style-name", default="", help="Nome do estilo visual utilizado")
    parser.add_argument("--style-family", default="", help="Familia de estilo visual (rotacao anti-repeticao)")
    parser.add_argument("--engines", default="", help="Motores usados separados por virgula")
    parser.add_argument("--materials", default="", help="Materiais 3D/visuais separados por virgula")
    parser.add_argument("--lessons", default="", help="Licoes aprendidas registradas com o video")
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    args = parse_args()
    video_path = Path(args.video)
    client_secrets = Path(args.client_secrets)
    token_path = Path(args.token)

    if len(args.title) > 100:
        print(f"[ERROR] Título excede 100 caracteres ({len(args.title)}).", flush=True)
        return 1
    if not args.dry_run and not video_path.exists():
        print(f"[ERROR] Vídeo não encontrado: {video_path}", flush=True)
        return 1

    try:
        creds, should_save = authenticate(client_secrets, token_path)
        youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
        channel_info = verify_channel(
            youtube,
            expected_handle=args.expected_handle,
            expected_channel=args.expected_channel,
            token_path=token_path,
        )

        # Só salva o token após validar que o canal é exatamente o esperado.
        if should_save or not token_path.exists():
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(creds.to_json(), encoding="utf-8")
            print(f"[AUTH] Token salvo com segurança em {token_path}", flush=True)

        if args.dry_run:
            print(f"[DRY-RUN] Canal verificado com sucesso: {channel_info}", flush=True)
            return 0

        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
        result = upload_video(
            youtube=youtube,
            video_path=video_path,
            title=args.title,
            description=args.description,
            tags=tags,
            category_id=args.category_id,
            privacy=args.privacy,
        )

        video_id = result.get("id", "")
        ret_status = (result.get("status") or {}).get("privacyStatus", "unknown")
        print(f"[OK] Upload concluído!", flush=True)
        print(f"video_id: {video_id}", flush=True)
        print(f"shorts_url: https://youtube.com/shorts/{video_id}", flush=True)
        print(f"watch_url: https://youtu.be/{video_id}", flush=True)
        print(f"privacyStatus: {ret_status}", flush=True)
        if args.privacy == "public" and ret_status != "public":
            print(
                "[NOTE] O YouTube manteve o vídeo como "
                f"'{ret_status}' (comum quando o app OAuth no Google Cloud está em modo Testing/não verificado).",
                flush=True,
            )

        if args.record_history and video_id:
            import json
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from editorial_memory import record_published_video

            topics_list = (
                json.loads(Path(args.topics_json).read_text(encoding="utf-8"))
                if args.topics_json
                else []
            )
            record_published_video(
                video_id=video_id,
                title=args.title,
                url=f"https://youtube.com/shorts/{video_id}",
                topics=topics_list,
                file_path=str(video_path),
                style_name=args.style_name,
                style_family=args.style_family,
                engines=[s.strip() for s in args.engines.split(",") if s.strip()],
                materials=[s.strip() for s in args.materials.split(",") if s.strip()],
                lessons=args.lessons,
            )
            print("[HISTORY] Publicação registrada em data/published_history.json", flush=True)
        return 0
    except HttpError as err:
        print(f"[HTTP_ERROR] status={getattr(err.resp, 'status', '?')} details={err}", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
