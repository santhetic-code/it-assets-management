import io
import qrcode
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter(tags=["QR Code"])


@router.get("/api/qr/{asset_tag}")
def generate_qr(asset_tag: str):
    qr = qrcode.QRCode(
        version=1,
        box_size=10,
        border=2,
    )
    qr.add_data(asset_tag)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr)
    img_byte_arr.seek(0)
    return StreamingResponse(img_byte_arr, media_type="image/png")
