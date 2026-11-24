from hashlib import sha256
import json
import re
from sqlalchemy.dialects.sqlite import insert
from . import document_service
from .balances import lock_writes
from .models import db, StockRequest
from .validation import ApiError

def movement(data, user, kind, request_key=None):
    """One commit for the receipt, all balances, items and audit entries.

    SQL increments prevent lost updates. A conditional SQL decrement checks the
    balance at write time, even when concurrent requests read an older value.
    """
    saved_request = None
    if request_key is not None:
        if not re.fullmatch(r'[A-Za-z0-9._-]{1,128}', request_key):
            raise ApiError('Некоректний ключ повтору операції.')
        try:
            encoded = json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
        except (ValueError, TypeError):
            raise ApiError('Некоректні дані операції.')
        fingerprint = sha256(encoded.encode()).hexdigest()
        # This INSERT obtains SQLite's write lock before changing any balances.
        # A concurrent duplicate waits, then sees the first committed response.
        claim = db.session.execute(insert(StockRequest).values(
            user_id=user.id, request_key=request_key, kind=kind, request_hash=fingerprint,
        ).on_conflict_do_nothing(index_elements=['user_id', 'request_key']))
        saved_request = db.session.get(StockRequest, (user.id, request_key))
        if claim.rowcount == 0:
            if saved_request.kind != kind or saved_request.request_hash != fingerprint:
                raise ApiError('Цей ключ уже використано для іншої операції.', 409)
            if saved_request.response_data is None:
                raise ApiError('Операція ще виконується. Спробуйте ще раз.', 409)
            return saved_request.response_data
    else:
        lock_writes()
    document = document_service.prepare(data, user, kind, quick=True)
    result = document_service.apply(document, user)
    response = dict(message='Надходження збережено.' if kind == 'receipt' else 'Списання збережено.',
                    items=result, receipt_id=document.receipt_id, document_id=document.id)
    if saved_request is not None:
        saved_request.response_data = response
    db.session.commit()
    return response
