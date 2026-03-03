import time
import sys
import pika
from app.core.config import settings

def wait_for_rabbit():
    connection = None
    retries = 10
    delay = 5  # seconds

    for i in range(retries):
        try:
            params = pika.URLParameters(settings.CELERY_BROKER_URL)
            connection = pika.BlockingConnection(params)
            connection.process_data_events()
            print(f"RabbitMQ is available. Connection successful.")
            return True
        except pika.exceptions.AMQPConnectionError as e:
            print(f"RabbitMQ not available, waiting {delay}s... ({i+1}/{retries}) Error: {e}")
            time.sleep(delay)
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            time.sleep(delay)
        finally:
            if connection:
                connection.close()

    print("RabbitMQ not available after multiple retries. Exiting.")
    return False

if __name__ == '__main__':
    if not wait_for_rabbit():
        sys.exit(1)
