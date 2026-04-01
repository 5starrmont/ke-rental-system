import africastalking
import logging

# Initialize Africa's Talking
# For testing, username is 'sandbox'
username = "sandbox" 
api_key = "YOUR_AT_API_KEY_HERE" # Get this from the AT Sandbox
africastalking.initialize(username, api_key)
sms = africastalking.SMS

logger = logging.getLogger(__name__)

def send_payment_confirmation(tenant, amount):
    """
    Sends a professional SMS to the tenant once payment is confirmed.
    """
    phone = tenant.phone_number
    # Ensure phone is in E.164 format (+254...)
    if not phone.startswith('+'):
        phone = f"+254{phone.lstrip('0')}"

    message = (
        f"Hello {tenant.name}, payment of KES {amount} received for Unit {tenant.unit.house_number}. "
        f"Your new balance is KES {tenant.balance}. Thank you!"
    )

    try:
        response = sms.send(message, [phone])
        logger.info(f"SMS Sent to {tenant.name}: {response}")
        return response
    except Exception as e:
        logger.error(f"SMS Failed for {tenant.name}: {str(e)}")
        return None