from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings, get_settings
from app.dependencies.database import DbSession
from app.models.enums import AccountSource, MT5ConnectionStatus
from app.models.models import MT5Connection, TradingAccount
from app.schemas.mt5 import CreateMt5ConnectionInput
from app.services.accounts import AccountsService, AccountsServiceDep
from app.utils.ids import generate_cuid
from app.utils.mt5_key import generate_connection_key, hash_connection_key
from app.utils.mt5_live_status import resolve_connection_live_status


class Mt5ConnectionService:
    def __init__(
        self,
        db: AsyncSession,
        accounts_service: AccountsService,
        settings: Settings,
    ) -> None:
        self._db = db
        self._accounts_service = accounts_service
        self._settings = settings

    def _get_secret(self) -> str:
        return self._settings.MT5_CONNECTION_TOKEN_SECRET or "development-mt5-secret"

    async def list_for_user(self, user_id: str) -> list[dict[str, object]]:
        result = await self._db.execute(
            select(MT5Connection)
            .where(MT5Connection.user_id == user_id)
            .options(selectinload(MT5Connection.trading_account))
            .order_by(MT5Connection.created_at.desc())
        )
        connections = result.scalars().all()
        return [self._to_response(connection) for connection in connections]

    async def create_for_user(
        self, user_id: str, input_data: CreateMt5ConnectionInput
    ) -> dict[str, object]:
        account = await self._accounts_service.find_by_id_for_user(
            input_data.trading_account_id, user_id
        )

        existing = await self._db.execute(
            select(MT5Connection).where(
                MT5Connection.trading_account_id == input_data.trading_account_id
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This trading account already has an MT5 connection.",
            )

        connection_key = generate_connection_key()
        secret = self._get_secret()
        connection = MT5Connection(
            id=generate_cuid(),
            user_id=user_id,
            trading_account_id=account.id,
            connection_key_hash=hash_connection_key(connection_key, secret),
            status=MT5ConnectionStatus.DISCONNECTED,
        )
        self._db.add(connection)
        account.source = AccountSource.MT5
        await self._db.commit()
        await self._db.refresh(connection, attribute_names=["trading_account"])

        return {
            "connection": self._to_response(connection),
            "connectionKey": connection_key,
        }

    async def revoke_for_user(self, connection_id: str, user_id: str) -> dict[str, bool]:
        connection = await self.find_by_id_for_user(connection_id, user_id)
        await self._db.delete(connection)
        await self._db.commit()
        return {"revoked": True}

    async def find_by_id_for_user(self, connection_id: str, user_id: str) -> MT5Connection:
        result = await self._db.execute(
            select(MT5Connection).where(MT5Connection.id == connection_id)
        )
        connection = result.scalar_one_or_none()

        if connection is None or connection.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="MT5 connection not found",
            )

        return connection

    async def find_by_trading_account_for_user(
        self, trading_account_id: str, user_id: str
    ) -> MT5Connection:
        await self._accounts_service.find_by_id_for_user(trading_account_id, user_id)

        result = await self._db.execute(
            select(MT5Connection).where(
                MT5Connection.trading_account_id == trading_account_id
            )
        )
        connection = result.scalar_one_or_none()

        if connection is None or connection.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="MT5 connection not found for this account.",
            )

        return connection

    async def assert_login_server_binding(
        self,
        connection: MT5Connection,
        mt5_login: str,
        server_name: str,
    ) -> None:
        if connection.mt5_login and connection.server_name:
            if connection.mt5_login != mt5_login or connection.server_name != server_name:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="MT5 login/server does not match the paired connection.",
                )
            return

        result = await self._db.execute(
            select(MT5Connection).where(
                MT5Connection.mt5_login == mt5_login,
                MT5Connection.server_name == server_name,
                MT5Connection.id != connection.id,
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This MT5 login and server are already paired to another account.",
            )

    def _to_response(self, connection: MT5Connection) -> dict[str, object]:
        trading_account = connection.trading_account
        return {
            "id": connection.id,
            "tradingAccountId": connection.trading_account_id,
            "tradingAccount": (
                {
                    "id": trading_account.id,
                    "name": trading_account.name,
                    "currency": trading_account.currency,
                    "source": trading_account.source.value,
                }
                if trading_account
                else None
            ),
            "mt5Login": connection.mt5_login,
            "serverName": connection.server_name,
            "brokerName": connection.broker_name,
            "status": connection.status.value,
            "lastHeartbeatAt": (
                connection.last_heartbeat_at.astimezone(UTC).isoformat()
                if connection.last_heartbeat_at
                else None
            ),
            "lastSyncedAt": (
                connection.last_synced_at.astimezone(UTC).isoformat()
                if connection.last_synced_at
                else None
            ),
            "lastPositionSnapshotAt": (
                connection.last_position_snapshot_at.astimezone(UTC).isoformat()
                if connection.last_position_snapshot_at
                else None
            ),
            "liveDataStatus": resolve_connection_live_status(
                last_heartbeat_at=connection.last_heartbeat_at
            ),
            "eaVersion": connection.ea_version,
            "createdAt": connection.created_at.astimezone(UTC).isoformat(),
            "updatedAt": connection.updated_at.astimezone(UTC).isoformat(),
        }


async def get_mt5_connection_service(
    db: DbSession,
    accounts_service: AccountsServiceDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Mt5ConnectionService:
    return Mt5ConnectionService(db, accounts_service, settings)


Mt5ConnectionServiceDep = Annotated[
    Mt5ConnectionService, Depends(get_mt5_connection_service)
]
