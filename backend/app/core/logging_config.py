import logging


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


# Role dans le projet:
# Ce fichier configure les logs Python. Il donne un format commun aux routes, pipelines et clients externes.
