from __future__ import annotations

import httpx
import structlog

from notification_billing.adapters.notifiers.base import BaseNotifier

logger = structlog.get_logger()


class MicrosoftGraphEmail(BaseNotifier):
    """
    Envia e-mails HTML usando a API do Microsoft Graph (sendMail).
    """

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        from_email: str,
    ):
        """
        Inicializa o notificador com as credenciais do Azure AD.

        Args:
            tenant_id: ID do seu diretório (locatário) do Azure.
            client_id: ID do seu aplicativo registrado no Azure.
            client_secret: Segredo do cliente para o aplicativo.
            from_email: O e-mail (User Principal Name) da conta que enviará a mensagem.
        """
        super().__init__("msgraph", "email")
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._client_secret = client_secret
        self._from_email = from_email
        self._auth_endpoint = f"https://login.microsoftonline.com/{self._tenant_id}/oauth2/v2.0/token"
        self._sendmail_endpoint = f"https://graph.microsoft.com/v1.0/users/{self._from_email}/sendMail"
        self._access_token = None

    def _get_access_token(self) -> str:
        """
        Obtém um token de acesso OAuth 2.0 usando o fluxo de credenciais do cliente.
        Idealmente, este token deveria ser cacheado até sua expiração.
        """
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        payload = {
            "client_id": self._client_id,
            "scope": "https://graph.microsoft.com/.default",
            "client_secret": self._client_secret,
            "grant_type": "client_credentials",
        }
        
        # Usamos um request síncrono simples para obter o token
        with httpx.Client() as client:
            response = client.post(self._auth_endpoint, data=payload, headers=headers)
            response.raise_for_status()  # Lança exceção para erros HTTP
            token_data = response.json()
            return token_data["access_token"]

    def send(
        self,
        recipients: list[str],
        subject: str,
        html: str,
        attachments: list[dict] | None = None,
    ) -> None:
        """
        Envia um e-mail transacional via Microsoft Graph API.

        - recipients: Lista de e-mails dos destinatários.
        - subject: Assunto do e-mail.
        - html: Conteúdo HTML do e-mail.
        - attachments: Lista de dicionários no formato Microsoft Graph.
        """
        try:
            if not recipients:
                return

            # Obtém um novo token para cada envio para simplificar.
            # Para produção, considere cachear o token.
            access_token = self._get_access_token()

            # O formato do payload é diferente do Brevo.
            # Documentação: https://learn.microsoft.com/pt-br/graph/api/user-sendmail
            payload = {
                "message": {
                    "subject": subject,
                    "body": {"contentType": "HTML", "content": html},
                    "toRecipients": [
                        {"emailAddress": {"address": r}} for r in recipients
                    ],
                    "attachments": [],
                },
                "saveToSentItems": "true", # Salva na pasta "Itens Enviados"
            }

            if attachments:
                payload["message"]["attachments"] = attachments

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            logger.debug("msgraph.payload", payload=payload)
            # Uso do método unificado de request
            self._request(
                "POST",
                self._sendmail_endpoint,
                json=payload,
                headers=headers,
            )

            logger.info(
                "email.sent",
                provider=self.provider,
                from_=self._from_email,
                recipients=len(recipients),
                subject=subject,
            )

        except httpx.HTTPStatusError as exc:
            # Tratamento de erro similar ao original
            resp = exc.response
            detail = resp.json() if "application/json" in resp.headers.get("content-type", "") else resp.text
            
            logger.error(
                "msgraph.error",
                status=resp.status_code,
                detail=detail,
            )
            raise