from http import HTTPStatus
from typing import Union, TYPE_CHECKING, Dict, Optional

import aiohttp

from ..models.id import daemonize
from ..helper import if_alive, error_msg_from
from .base import AsyncBaseClient
from .mixin import AsyncToSyncMixin

if TYPE_CHECKING:
    from ..models import DaemonID


class AsyncFlowClient(AsyncBaseClient):
    """Async Client to create/update/delete Flows on remote JinaD"""

    _kind = 'flow'
    _endpoint = '/flows'

    @if_alive
    async def arguments(self) -> Optional[Dict]:
        """Get all arguments accepted by a remote Pea/Pod

        :return: dict arguments of remote JinaD
        """
        async with aiohttp.request(
            method='GET', url=f'{self.store_api}/arguments'
        ) as response:
            if response.status == HTTPStatus.OK:
                return await response.json()

    @if_alive
    async def create(
        self, workspace_id: 'DaemonID', filename: str, *args, **kwargs
    ) -> str:
        """Start a Flow on remote JinaD

        :param workspace_id: workspace id where flow will be created
        :param filename: name of the flow yaml file in the workspace
        :param args: positional args
        :param kwargs: keyword args
        :return: flow id
        """
        async with aiohttp.request(
            method='POST',
            url=self.store_api,
            params={'workspace_id': workspace_id, 'filename': filename},
        ) as response:
            response_json = await response.json()
            if response.status != HTTPStatus.CREATED:
                error_msg = error_msg_from(response_json)
                self._logger.error(
                    f'{self._kind.title()} creation failed as: {error_msg}'
                )
                return error_msg
            return response_json

    @if_alive
    async def delete(self, id: Union[str, 'DaemonID'], *args, **kwargs) -> bool:
        """Terminate a Flow on remote JinaD

        :param id: flow id
        :param args: positional args
        :param kwargs: keyword args
        :return: True if deletion is successful
        """
        async with aiohttp.request(
            method='DELETE',
            url=f'{self.store_api}/{daemonize(id, self._kind)}',
        ) as response:
            response_json = await response.json()
            if response.status != HTTPStatus.OK:
                self._logger.error(
                    f'deletion of {self._kind.title()} {id} failed: {error_msg_from(response_json)}'
                )
            return response.status == HTTPStatus.OK


class FlowClient(AsyncToSyncMixin, AsyncFlowClient):
    """Client to create/update/delete Flows on remote JinaD"""
