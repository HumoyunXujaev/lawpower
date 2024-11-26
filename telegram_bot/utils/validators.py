import re
from typing import Optional, Union, Any
from datetime import datetime
from decimal import Decimal
import phonenumbers
import logging

logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """Base validation error"""
    pass

class Validator:
    @staticmethod
    def phone_number(
        phone: str,
        country_code: str = 'UZ'
    ) -> Optional[str]:
        """Validate and format phone number"""
        try:
            # Parse phone number
            parsed = phonenumbers.parse(phone, country_code)
            
            # Check if valid
            if not phonenumbers.is_valid_number(parsed):
                raise ValidationError("Invalid phone number")
            
            # Format to international format
            return phonenumbers.format_number(
                parsed,
                phonenumbers.PhoneNumberFormat.E164
            )
        except Exception as e:
            logger.error(f"Phone validation error: {e}")
            raise ValidationError("Invalid phone number format")
    
    @staticmethod
    def amount(
        amount: Union[str, int, float, Decimal],
        min_value: Optional[Decimal] = None,
        max_value: Optional[Decimal] = None
    ) -> Decimal:
        """Validate payment amount"""
        try:
            # Convert to Decimal
            if isinstance(amount, str):
                amount = Decimal(amount.replace(',', '.'))
            else:
                amount = Decimal(str(amount))
            
            # Check range
            if min_value and amount < min_value:
                raise ValidationError(
                    f"Amount must be at least {min_value}"
                )
            if max_value and amount > max_value:
                raise ValidationError(
                    f"Amount must be at most {max_value}"
                )
            
            return amount
            
        except (TypeError, ValueError) as e:
            logger.error(f"Amount validation error: {e}")
            raise ValidationError("Invalid amount format")
    
    @staticmethod
    def text_length(
        text: str,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None
    ) -> str:
        """Validate text length"""
        if min_length and len(text) < min_length:
            raise ValidationError(
                f"Text must be at least {min_length} characters"
            )
        if max_length and len(text) > max_length:
            raise ValidationError(
                f"Text must be at most {max_length} characters"
            )
        return text
    
    @staticmethod
    def datetime(
        dt: Union[str, datetime],
        min_date: Optional[datetime] = None,
        max_date: Optional[datetime] = None,
        format: str = '%Y-%m-%d %H:%M:%S'
    ) -> datetime:
        """Validate datetime"""
        try:
            # Convert string to datetime if needed
            if isinstance(dt, str):
                dt = datetime.strptime(dt, format)
            
            # Check range
            if min_date and dt < min_date:
                raise ValidationError(
                    f"Date must be after {min_date.strftime(format)}"
                )
            if max_date and dt > max_date:
                raise ValidationError(
                    f"Date must be before {max_date.strftime(format)}"
                )
            
            return dt
            
        except ValueError as e:
            logger.error(f"Datetime validation error: {e}")
            raise ValidationError(f"Invalid datetime format, expected {format}")

    @staticmethod
    def email(email: str) -> str:
        """Validate email address"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            raise ValidationError("Invalid email address")
        return email.lower()

    @staticmethod
    def language(lang: str) -> str:
        """Validate language code"""
        valid_languages = {'uz', 'ru'}
        if lang.lower() not in valid_languages:
            raise ValidationError(
                f"Invalid language code. Must be one of: {', '.join(valid_languages)}"
            )
        return lang.lower()

    @staticmethod
    def boolean(value: Any) -> bool:
        """Validate and convert boolean value"""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            value = value.lower()
            if value in ('true', '1', 't', 'y', 'yes'):
                return True
            if value in ('false', '0', 'f', 'n', 'no'):
                return False
        raise ValidationError("Invalid boolean value")

    @staticmethod
    def telegram_username(username: str) -> str:
        """Validate Telegram username"""
        pattern = r'^@?[a-zA-Z0-9_]{5,32}$'
        if not re.match(pattern, username):
            raise ValidationError(
                "Invalid Telegram username. Must be 5-32 characters long and contain only letters, numbers and underscore"
            )
        return username.lstrip('@')

    @staticmethod
    def payment_data(data: dict) -> dict:
        """Validate payment data"""
        required_fields = {'amount', 'provider'}
        missing_fields = required_fields - set(data.keys())
        if missing_fields:
            raise ValidationError(
                f"Missing required payment fields: {', '.join(missing_fields)}"
            )
        
        # Validate amount
        data['amount'] = Validator.amount(
            data['amount'],
            min_value=Decimal('1000.00')
        )
        
        # Validate provider
        valid_providers = {'click', 'payme'}
        if data['provider'].lower() not in valid_providers:
            raise ValidationError(
                f"Invalid payment provider. Must be one of: {', '.join(valid_providers)}"
            )
        
        return data

    @staticmethod 
    def question_data(data: dict) -> dict:
        """Validate question data"""
        required_fields = {'text', 'language'}
        missing_fields = required_fields - set(data.keys())
        if missing_fields:
            raise ValidationError(
                f"Missing required question fields: {', '.join(missing_fields)}"
            )
        
        # Validate text
        data['text'] = Validator.text_length(
            data['text'],
            min_length=10,
            max_length=1000
        )
        
        # Validate language
        data['language'] = Validator.language(data['language'])
        
        return data

    @staticmethod
    def consultation_data(data: dict) -> dict:
        """Validate consultation data"""
        required_fields = {'phone_number', 'problem_description'}
        missing_fields = required_fields - set(data.keys())
        if missing_fields:
            raise ValidationError(
                f"Missing required consultation fields: {', '.join(missing_fields)}"
            )
        
        # Validate phone
        data['phone_number'] = Validator.phone_number(data['phone_number'])
        
        # Validate description
        data['problem_description'] = Validator.text_length(
            data['problem_description'],
            min_length=20,
            max_length=2000
        )
        
        # Validate scheduled time if present
        if 'scheduled_time' in data:
            data['scheduled_time'] = Validator.datetime(
                data['scheduled_time'],
                min_date=datetime.now()
            )
        
        return data

# Helper functions for request validation
def validate_request(validator_func: callable):
    """Decorator for request validation"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                # Find request data in args or kwargs
                request_data = None
                for arg in args:
                    if isinstance(arg, dict):
                        request_data = arg
                        break
                if not request_data:
                    request_data = kwargs.get('data')
                
                if request_data:
                    # Validate data
                    validated_data = validator_func(request_data)
                    
                    # Update args or kwargs
                    if 'data' in kwargs:
                        kwargs['data'] = validated_data
                    else:
                        args = list(args)
                        for i, arg in enumerate(args):
                            if isinstance(arg, dict):
                                args[i] = validated_data
                                break
                        args = tuple(args)
                
                return await func(*args, **kwargs)
                
            except ValidationError as e:
                logger.error(f"Validation error: {e}")
                raise
                
        return wrapper
    return decorator

# Create validator instance
validator = Validator()