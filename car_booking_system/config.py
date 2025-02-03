import os

class Config:
    # General Configurations
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your_default_secret_key'

    # MySQL Configuration
    MYSQL_HOST = 'localhost'  # Host of the MySQL database
    MYSQL_USER = 'root'  # MySQL username
    MYSQL_PASSWORD = 'your_password'  # MySQL password
    MYSQL_DB = 'car_booking_system'  # MySQL database name

    # SQLAlchemy Configuration (optional, if using Flask-SQLAlchemy)
    SQLALCHEMY_DATABASE_URI = f'mysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}/{MYSQL_DB}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # Disable tracking modifications to save resources

    # Email Configuration (for sending booking confirmations)
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')  # Email for sending notifications
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')  # Password for the email

    # Other settings (optional)
    CAR_BOOKING_TIME_LIMIT = 24  # Time limit in hours for booking confirmation
    MAX_CARS_AVAILABLE = 50  # Max number of cars available for booking

# Config class can be extended if you need environment-specific configurations.
