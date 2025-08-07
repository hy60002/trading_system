"""
Enhanced Trading System Exceptions
Author: Enhanced by Claude Code
Version: 4.0
"""

import logging
from typing import Optional, Any, Dict
from datetime import datetime

logger = logging.getLogger(__name__)

class TradingSystemException(Exception):
    """Base exception for trading system with enhanced error tracking"""
    
    def __init__(self, message: str, error_code: Optional[str] = None, 
                 context: Optional[Dict[str, Any]] = None, original_error: Optional[Exception] = None):
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.context = context or {}
        self.original_error = original_error
        self.timestamp = datetime.utcnow()
        
        # Enhanced error message
        full_message = f"[{self.error_code}] {message}"
        if context:
            full_message += f" | Context: {context}"
        if original_error:
            full_message += f" | Original: {str(original_error)}"
            
        super().__init__(full_message)
        
        # Log the error
        logger.error(f"TradingSystemException: {full_message}", 
                    extra={'error_code': self.error_code, 'context': self.context})

class ConfigurationError(TradingSystemException):
    """Configuration related errors"""
    
    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs):
        context = kwargs.get('context', {})
        if config_key:
            context['config_key'] = config_key
        kwargs['context'] = context
        super().__init__(message, **kwargs)

class ExchangeConnectionError(TradingSystemException):
    """Exchange connection and API errors"""
    
    def __init__(self, message: str, exchange: Optional[str] = None, 
                 status_code: Optional[int] = None, **kwargs):
        context = kwargs.get('context', {})
        if exchange:
            context['exchange'] = exchange
        if status_code:
            context['status_code'] = status_code
        kwargs['context'] = context
        super().__init__(message, **kwargs)

class ExchangeAPIError(ExchangeConnectionError):
    """Specific exchange API errors"""
    pass

class ExchangeRateLimitError(ExchangeConnectionError):
    """Exchange rate limit exceeded"""
    
    def __init__(self, message: str, retry_after: Optional[int] = None, **kwargs):
        context = kwargs.get('context', {})
        if retry_after:
            context['retry_after'] = retry_after
        kwargs['context'] = context
        super().__init__(message, **kwargs)

class TradingError(TradingSystemException):
    """Trading execution errors"""
    
    def __init__(self, message: str, symbol: Optional[str] = None, 
                 order_id: Optional[str] = None, **kwargs):
        context = kwargs.get('context', {})
        if symbol:
            context['symbol'] = symbol
        if order_id:
            context['order_id'] = order_id
        kwargs['context'] = context
        super().__init__(message, **kwargs)

class InsufficientFundsError(TradingError):
    """Insufficient funds for trading"""
    
    def __init__(self, message: str, required_amount: Optional[float] = None, 
                 available_amount: Optional[float] = None, **kwargs):
        context = kwargs.get('context', {})
        if required_amount:
            context['required_amount'] = required_amount
        if available_amount:
            context['available_amount'] = available_amount
        kwargs['context'] = context
        super().__init__(message, **kwargs)

class RiskLimitExceededError(TradingError):
    """Risk management limits exceeded"""
    
    def __init__(self, message: str, risk_type: Optional[str] = None, 
                 current_value: Optional[float] = None, limit_value: Optional[float] = None, **kwargs):
        context = kwargs.get('context', {})
        if risk_type:
            context['risk_type'] = risk_type
        if current_value:
            context['current_value'] = current_value
        if limit_value:
            context['limit_value'] = limit_value
        kwargs['context'] = context
        super().__init__(message, **kwargs)

class PositionLimitError(TradingError):
    """Position limit exceeded"""
    pass

class DataError(TradingSystemException):
    """Data processing and validation errors"""
    
    def __init__(self, message: str, data_type: Optional[str] = None, 
                 data_source: Optional[str] = None, **kwargs):
        context = kwargs.get('context', {})
        if data_type:
            context['data_type'] = data_type
        if data_source:
            context['data_source'] = data_source
        kwargs['context'] = context
        super().__init__(message, **kwargs)

class InvalidDataFormatError(DataError):
    """Invalid data format error"""
    pass

class MissingDataError(DataError):
    """Required data missing"""
    pass

class StaleDataError(DataError):
    """Data is too old/stale"""
    
    def __init__(self, message: str, data_age: Optional[int] = None, 
                 max_age: Optional[int] = None, **kwargs):
        context = kwargs.get('context', {})
        if data_age:
            context['data_age'] = data_age
        if max_age:
            context['max_age'] = max_age
        kwargs['context'] = context
        super().__init__(message, **kwargs)

class DatabaseError(TradingSystemException):
    """Database operation errors"""
    
    def __init__(self, message: str, operation: Optional[str] = None, 
                 table: Optional[str] = None, **kwargs):
        context = kwargs.get('context', {})
        if operation:
            context['operation'] = operation
        if table:
            context['table'] = table
        kwargs['context'] = context
        super().__init__(message, **kwargs)

class DatabaseConnectionError(DatabaseError):
    """Database connection error"""
    pass

class DatabaseQueryError(DatabaseError):
    """Database query execution error"""
    pass

class WebSocketError(TradingSystemException):
    """WebSocket connection and communication errors"""
    
    def __init__(self, message: str, connection_id: Optional[str] = None, 
                 reconnect_attempts: Optional[int] = None, **kwargs):
        context = kwargs.get('context', {})
        if connection_id:
            context['connection_id'] = connection_id
        if reconnect_attempts:
            context['reconnect_attempts'] = reconnect_attempts
        kwargs['context'] = context
        super().__init__(message, **kwargs)

class AnalysisError(TradingSystemException):
    """Technical analysis and ML model errors"""
    
    def __init__(self, message: str, analysis_type: Optional[str] = None, 
                 model_name: Optional[str] = None, **kwargs):
        context = kwargs.get('context', {})
        if analysis_type:
            context['analysis_type'] = analysis_type
        if model_name:
            context['model_name'] = model_name
        kwargs['context'] = context
        super().__init__(message, **kwargs)

class ModelError(AnalysisError):
    """Machine learning model errors"""
    pass

class IndicatorError(AnalysisError):
    """Technical indicator calculation errors"""
    pass

class NotificationError(TradingSystemException):
    """Notification system errors"""
    
    def __init__(self, message: str, notification_type: Optional[str] = None, 
                 recipient: Optional[str] = None, **kwargs):
        context = kwargs.get('context', {})
        if notification_type:
            context['notification_type'] = notification_type
        if recipient:
            context['recipient'] = recipient
        kwargs['context'] = context
        super().__init__(message, **kwargs)

class ValidationError(TradingSystemException):
    """Input validation errors"""
    
    def __init__(self, message: str, field_name: Optional[str] = None, 
                 field_value: Optional[Any] = None, **kwargs):
        context = kwargs.get('context', {})
        if field_name:
            context['field_name'] = field_name
        if field_value is not None:
            context['field_value'] = str(field_value)
        kwargs['context'] = context
        super().__init__(message, **kwargs)

class SecurityError(TradingSystemException):
    """Security and authentication errors"""
    
    def __init__(self, message: str, security_event: Optional[str] = None, 
                 user_id: Optional[str] = None, **kwargs):
        context = kwargs.get('context', {})
        if security_event:
            context['security_event'] = security_event
        if user_id:
            context['user_id'] = user_id
        kwargs['context'] = context
        super().__init__(message, **kwargs)

class AuthenticationError(SecurityError):
    """Authentication failed"""
    pass

class AuthorizationError(SecurityError):
    """Authorization failed"""
    pass

class RateLimitError(SecurityError):
    """Rate limit exceeded"""
    pass

# Exception handler decorator
def handle_exceptions(default_return=None, reraise=True):
    """Decorator to handle exceptions with logging"""
    
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except TradingSystemException:
                # Our exceptions are already logged
                if reraise:
                    raise
                return default_return
            except Exception as e:
                # Wrap unknown exceptions
                wrapped_error = TradingSystemException(
                    f"Unexpected error in {func.__name__}: {str(e)}",
                    error_code="UNEXPECTED_ERROR",
                    context={'function': func.__name__, 'args': str(args)[:100]},
                    original_error=e
                )
                if reraise:
                    raise wrapped_error
                return default_return
        return wrapper
    return decorator

# Async exception handler decorator
def handle_async_exceptions(default_return=None, reraise=True):
    """Decorator to handle exceptions in async functions"""
    
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except TradingSystemException:
                # Our exceptions are already logged
                if reraise:
                    raise
                return default_return
            except Exception as e:
                # Wrap unknown exceptions
                wrapped_error = TradingSystemException(
                    f"Unexpected error in {func.__name__}: {str(e)}",
                    error_code="UNEXPECTED_ERROR",
                    context={'function': func.__name__, 'args': str(args)[:100]},
                    original_error=e
                )
                if reraise:
                    raise wrapped_error
                return default_return
        return wrapper
    return decorator