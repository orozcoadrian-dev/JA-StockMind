"""FastAPI application package."""


def __getattr__(name):
	if name == "app":
		from .main import app

		return app
	raise AttributeError(name)