from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from app.core.config import settings
from pydantic import EmailStr

conf = ConnectionConfig(
    MAIL_USERNAME=settings.SMTP_USER,
    MAIL_PASSWORD=settings.SMTP_PASS,
    MAIL_FROM=settings.SMTP_FROM or settings.SMTP_USER,
    MAIL_PORT=settings.SMTP_PORT,
    MAIL_SERVER=settings.SMTP_HOST,
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)

async def send_otp_email(email: str, code: str, type: str):
    subject = (
        "Peergraph Intelligence | Initialization Sequence"
        if type == "signup"
        else "Peergraph Intelligence | Recovery Sequence"
    )
    
    message_text = (
        f"Your initialization sequence code is: {code}. This code expires in 10 minutes."
        if type == "signup"
        else f"Your recovery sequence code is: {code}. This code expires in 10 minutes."
    )
    
    html = f"""
    <div style="font-family: sans-serif; background-color: #09090b; color: #ffffff; padding: 40px; border-radius: 16px; max-width: 600px; margin: auto; border: 1px solid #27272a;">
      <h1 style="color: #00BC7D; font-size: 24px; font-weight: 900; letter-spacing: -0.05em; text-transform: uppercase;">Peergraph Hub</h1>
      <p style="font-size: 16px; color: #a1a1aa; margin-top: 24px;">Sequence verification requested for: <strong>{email}</strong></p>
      <div style="background-color: #18181b; padding: 32px; border-radius: 12px; margin-top: 32px; text-align: center; border: 1px solid #3f3f46;">
        <span style="font-size: 48px; font-weight: 900; letter-spacing: 0.5em; color: #ffffff; margin-left: 0.5em;">{code}</span>
      </div>
      <p style="font-size: 12px; color: #71717a; margin-top: 32px; text-transform: uppercase; letter-spacing: 0.1em;">
        {message_text}
      </p>
      <div style="margin-top: 40px; border-top: 1px solid #27272a; padding-top: 24px;">
        <p style="font-size: 10px; color: #52525b; text-transform: uppercase; letter-spacing: 0.05em;">Institutional Node Verification Protocol v1.0</p>
      </div>
    </div>
    """
    
    message = MessageSchema(
        subject=subject,
        recipients=[email],
        body=html,
        subtype=MessageType.html
    )

    fm = FastMail(conf)
    await fm.send_message(message)
