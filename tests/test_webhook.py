import unittest

from aiohttp import web

from discord_bot import webhook


class WebhookTests(unittest.IsolatedAsyncioTestCase):
    """Runs the webhook client against a local fake of Discord's webhook endpoint."""

    async def asyncSetUp(self):
        self.received = []
        self.post_status = 204

        async def handle_get(request):
            return web.json_response({"channel_id": "1234"})

        async def handle_post(request):
            self.received.append(await request.json())
            return web.Response(status=self.post_status, text="" if self.post_status == 204 else "bad")

        app = web.Application()
        app.router.add_get("/hook", handle_get)
        app.router.add_post("/hook", handle_post)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        self.url = f"http://127.0.0.1:{port}/hook"

    async def asyncTearDown(self):
        await self.runner.cleanup()

    async def test_get_channel_id(self):
        self.assertEqual(await webhook.get_webhook_channel_id(self.url), 1234)

    async def test_send_message_success_blocks_mass_pings(self):
        self.assertTrue(await webhook.send_message("hi @everyone", self.url))
        self.assertEqual(self.received[0]["content"], "hi @everyone")
        self.assertEqual(self.received[0]["allowed_mentions"], {"parse": ["users"]})

    async def test_send_message_failure_returns_false(self):
        self.post_status = 400
        with self.assertLogs("discord_bot.webhook", level="ERROR"):
            self.assertFalse(await webhook.send_message("hi", self.url))


if __name__ == "__main__":
    unittest.main()
