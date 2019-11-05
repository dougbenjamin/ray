import logging
from aiohttp import web
from .baseCommunicator import BaseCommunicator
from urllib.parse import parse_qs
import asyncio
import uvloop

logger = logging.getLogger(__name__)


class AsyncRouter:

    def __init__(self):
        self.routes = dict()

    def register(self, endpoint, handler):
        self.routes[endpoint] = handler

    async def route(self, endpoint, *args, **kwargs):
        if self.routes.get(endpoint) is None:
            raise Exception(f"Route {endpoint} not registered")
        return await self.routes[endpoint](*args, **kwargs)


class Actor(BaseCommunicator):

    def __init__(self, actor, config):
        super().__init__(actor, config)
        self.host = '0.0.0.0'
        self.port = 8080
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        self.loop = asyncio.get_event_loop()

        self.router = AsyncRouter()
        self.router.register('/server/panda/getJob', self.handle_getJob)
        self.router.register('/server/panda/updateJob', self.handle_updateJob)
        self.router.register('/server/panda/updateJobsInBulk', self.handle_updateJobsInBulk)
        self.router.register('/server/panda/getStatus', self.handle_getStatus)
        self.router.register('/server/panda/getEventRanges', self.handle_getEventRanges)
        self.router.register('/server/panda/updateEventRanges', self.handle_updateEventRanges)
        self.router.register('/server/panda/getKeyPair', self.handle_getkeyPair)

    def start(self):
        self.run(False)

    def stop(self):
        self.loop.run_until_complete(self.stop_server())

    def fix_command(self, command):
        return command

    async def http_handler(self, request: web.BaseRequest):
        logging.debug(f"Routing {request.method} {request.path}")
        return await self.router.route(request.path, request=request)

    async def handle_getJob(self, request):
        if request.can_read_body:
            body = await request.text()
            body = parse_qs(body)
            logging.debug(f"Body: {body}")
        logger.debug(f"Serving job {self.actor.job}")
        return web.json_response(self.actor.job)

    async def handle_updateJob(self, request):
        body = str()
        if request.can_read_body:
            body = await request.json()
            logging.debug(f"Body: {body}")
        return body

    async def handle_updateJobsInBulk(self, request):
        raise NotImplementedError(f"{request.path} handler not implemented")

    async def handle_getStatus(self, request):
        raise NotImplementedError(f"{request.path} handler not implemented")

    async def handle_getEventRanges(self, request):
        raise NotImplementedError(f"{request.path} handler not implemented")

    async def handle_updateEventRanges(self, request):
        raise NotImplementedError(f"{request.path} handler not implemented")

    async def handle_getkeyPair(self, request):
        raise NotImplementedError(f"{request.path} handler not implemented")

    async def startup_server(self) -> web.TCPSite:
        server = web.Server(self.http_handler)
        runner = web.ServerRunner(server)
        await runner.setup()
        self.site = web.TCPSite(runner, self.host, self.port)
        await self.site.start()
        logging.debug(f"======= Serving on http://{self.host}:{self.port}/ ======")
        return self.site

    async def stop_server(self):
        self.should_stop = True
        if self.site:
            logging.debug(f"======= Stopped http://{self.host}:{self.port}/ ======")
            await self.site.stop()

    async def serve(self, block: bool = True):
        await self.startup_server()
        self.should_stop = False
        if not block:
            return
        while not self.should_stop:
            await asyncio.sleep(1)

    def run(self, block: bool = True):
        self.loop.run_until_complete(self.serve(block))
