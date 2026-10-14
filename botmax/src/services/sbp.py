"""Система Быстрых Платежей (СБП) - Сервис генерации QR-кодов и обработки платежей"""

import base64
import hashlib
import hmac
import io
import logging
import uuid
from typing import Dict, Any, Optional
import qrcode
from qrcode.image.pil import PilImage

logger = logging.getLogger("botmax.sbp")


class SBPService:
    """SBP (Система Быстрых Платежей) payment service for Russia NSPK standards"""

    def __init__(self, merchant_id: str = "test_merchant", secret_key: str = "test_secret"):
        self.merchant_id = merchant_id
        self.secret_key = secret_key

    def generate_qrid(self) -> str:
        """Generate official-like NSPK QR identifier"""
        raw = uuid.uuid4().hex.upper()
        return f"AD1000{raw[:26]}"

    def create_payment_payload(
        self,
        order_id: str,
        amount_rub: float,
        purpose: str,
        recipient_phone: str = "",
        recipient_bank: str = "СБП",
        custom_qr_url: str = "",
    ) -> Dict[str, Any]:
        """
        Generate SBP payment payload conforming to NSPK QR standard.
        Pre-embeds order ID / purpose into URLs and QR codes so participants don't have to type it manually.
        amount_rub: Amount in Russian Rubles
        purpose: Payment description / purpose
        recipient_phone: Organizer phone for direct bank transfer links
        recipient_bank: Organizer bank name
        custom_qr_url: Organizer static QR URL or bank transfer link
        """
        import re
        import urllib.parse

        qrid = self.generate_qrid()
        sum_kopecks = int(round(amount_rub * 100))
        encoded_purpose = urllib.parse.quote_plus(order_id)

        # Standard NSPK QR link with embedded order comment and purpose
        nspk_url = (
            f"https://qr.nspk.ru/{qrid}?"
            f"type=02&bank=100000000111&sum={sum_kopecks}&cur=RUB"
            f"&description={encoded_purpose}&purpose={encoded_purpose}"
        )

        # Deep link to open installed Russian banking apps (СБП) with embedded comment
        deep_link = (
            f"sbp://qr.nspk.ru/{qrid}?type=02&sum={sum_kopecks}&cur=RUB"
            f"&description={encoded_purpose}&purpose={encoded_purpose}"
        )

        # Clean digits-only phone for direct Russian banking apps (T-Bank, Sber)
        clean_phone = re.sub(r"\D", "", recipient_phone or "")
        if clean_phone.startswith("8") and len(clean_phone) == 11:
            clean_phone = "7" + clean_phone[1:]
        elif len(clean_phone) == 10:
            clean_phone = "7" + clean_phone

        # Direct prefilled T-Bank link (automatically fills recipient phone, amount, and comment!)
        tbank_url = ""
        if clean_phone:
            tbank_url = (
                f"https://www.tbank.ru/rm/{clean_phone}/"
                f"?amount={amount_rub:.2f}&comment={urllib.parse.quote_plus(order_id)}"
            )

        # Direct prefilled Sberbank link
        sber_url = ""
        if clean_phone:
            sber_url = (
                f"https://www.sberbank.com/sms/p2p"
                f"?phone={clean_phone}&amount={int(round(amount_rub))}&comment={urllib.parse.quote_plus(order_id)}"
            )

        # Generate working QR code for smartphone scanning
        # 1. If organizer provided their own personal SBP QR code or link, use that directly
        if custom_qr_url and custom_qr_url.strip():
            target_str = custom_qr_url.strip()
            if target_str.startswith("data:image"):
                qr_data_url = target_str
            else:
                qr_data_url = self.generate_qr_code_data_url(target_str)
        else:
            # 2. Otherwise encode direct bank transfer link (T-Bank or Sber)
            is_sber = "сбер" in (recipient_bank or "").lower()
            qr_target = (sber_url if is_sber and sber_url else tbank_url) if (tbank_url or sber_url) else nspk_url
            qr_data_url = self.generate_qr_code_data_url(qr_target)

        return {
            "qrid": qrid,
            "order_id": order_id,
            "nspk_url": nspk_url,
            "deep_link": deep_link,
            "tbank_url": tbank_url,
            "sber_url": sber_url,
            "recipient_phone": recipient_phone,
            "recipient_bank": recipient_bank,
            "qr_data_url": qr_data_url,
            "sum_kopecks": sum_kopecks,
            "amount_rub": amount_rub,
            "purpose": purpose,
            "payment_code": order_id,
        }

    def generate_qr_code_data_url(self, data: str) -> str:
        """Generate high-resolution PNG Base64 Data URL for QR Code"""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
        )
        qr.add_data(data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="#001833", back_color="#FFFFFF")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        b64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{b64_str}"

    def verify_webhook_signature(
        self, payload_bytes: bytes, signature: str
    ) -> bool:
        """Verify HMAC-SHA256 signature from bank webhook"""
        if not signature or not self.secret_key:
            return False
        expected = hmac.new(
            self.secret_key.encode("utf-8"), payload_bytes, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
