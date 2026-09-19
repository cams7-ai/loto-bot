from __future__ import annotations

import os
import tempfile
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

TERMS_OF_USE_URL = "https://www.loteriasonline.caixa.gov.br/silce-web/#/termos-de-uso"
EXPECTED_HOST = "www.loteriasonline.caixa.gov.br"
EXPECTED_PATH = "/silce-web/"
EXPECTED_FRAGMENT = "/termos-de-uso"
NAVIGATION_SETTLE_MS = 5_000


def main() -> None:
    proxy_server = os.getenv("BROWSER_PROXY_SERVER")

    if not proxy_server:
        raise RuntimeError("BROWSER_PROXY_SERVER não configurado")

    with tempfile.TemporaryDirectory(prefix="lotobot-proxy-test-") as profile_dir, sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True,
            proxy={
                "server": proxy_server,
            },
        )

        try:
            page = context.pages[0] if context.pages else context.new_page()

            response = page.goto(
                TERMS_OF_USE_URL,
                wait_until="commit",
                timeout=30_000,
            )

            if response is None or not response.ok:
                status = "sem resposta" if response is None else str(response.status)
                raise RuntimeError(f"A página da CAIXA retornou um status inválido: {status}")

            # DOMContentLoaded pode não ocorrer enquanto o portal processa scripts
            # e desafios de proteção. Aguarde os redirecionamentos sem vincular o
            # teste a esse evento global da página.
            page.wait_for_timeout(NAVIGATION_SETTLE_MS)

            current_url = urlsplit(page.url)
            if (
                current_url.hostname != EXPECTED_HOST
                or current_url.path != EXPECTED_PATH
                or current_url.fragment != EXPECTED_FRAGMENT
            ):
                raise RuntimeError(f"O Chromium terminou em uma URL inesperada: {page.url}")

            body = page.locator("body")
            body.wait_for(state="attached", timeout=30_000)
            if not body.inner_html().strip():
                raise RuntimeError("A página da CAIXA retornou um documento sem conteúdo")

            print("Teste CAIXA via Chromium: OK")
            print(f"Status HTTP CAIXA: {response.status}")
            print(f"URL final CAIXA: {page.url}")
            print(f"Título da página CAIXA: {page.title()}")
        finally:
            context.close()


if __name__ == "__main__":
    main()
