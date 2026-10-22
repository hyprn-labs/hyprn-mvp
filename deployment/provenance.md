# Deployment verification tools

## Docker CLI for isolated Linux acceptance

The existing `docker_cli_image` pin selects Docker's official CLI image. The
Linux acceptance fixture uses its Docker executable to exercise the real engine;
it does not install another daemon or include this image in the product payload.

- Version: `29.8.2-cli`.
- Official image source: `docker-library/docker`, commit
  `cdef894c37a7e2912441bd2fbcf6f6c738628559`, `29/cli/Dockerfile`.
- Index: `sha256:35cfcf893c20f2931f4909151b5407aaaeab711277de7ce8b8f521f095d54c32`.
- Linux amd64 manifest:
  `sha256:d329fa64f42e03248f9a6cb2e21b6d4aa4d76f5a80aa2ad7946d81fbf1860602`.
- CLI source/license: https://github.com/docker/cli/tree/v29.8.2;
  Apache-2.0. Tagged `LICENSE` SHA-256:
  `2d81ea060825006fc8f3fe28aa5dc0ffeb80faf325b612c955229157b8c10dc0`.
- Official image Dockerfile SHA-256:
  `62f1d13560224aa72c494a9cf8d4a1be95f359af32f43136c59799d479cb919c`.

The manifest, exact source and license were checked before acquisition. This
license record concerns the CLI; it does not classify the entire Alpine image
or authorize redistributing its unrelated packages. If a future product payload
includes the CLI, retain its notices and audit the shipped dependency closure.
