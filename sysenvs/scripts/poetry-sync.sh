#!/usr/bin/env bash
# Enable bash's unofficial strict mode
GITROOT=$(git rev-parse --show-toplevel)
# shellcheck disable=SC1090,SC1091
. "${GITROOT}"/scripts/lib/strict-mode
# shellcheck disable=SC1090,SC1091
. "${GITROOT}"/scripts/lib/utils
strictMode

THIS_SCRIPT=$(basename "${0}")
THUNDER_PACKGE_NAME='infra-thunder'

function usage () {
  echo "Usage:"
  echo "${THIS_SCRIPT} -u, --update <poetry update instead of poetry install. OPTIONAL>"
  echo
  echo "Removes ${THUNDER_PACKGE_NAME} and either installs or updates virtual environment using poetry"
  exit 1
}

# Ensure dependencies are present
if ! command -v poetry &> /dev/null; then
  msg_fatal "[-] Dependencies unmet. Please verify that the following are installed and in the PATH: poetry. Check README for requirements"
fi

ACTION='install'
while [[ $# -gt 0 ]]; do
  case "${1}" in
    -u|--update)
      ACTION='update'
      shift # past argument
      ;;
    -*)
      msg_error "Unknown option ${1}"
      usage
      ;;
  esac
done

poetry run pip uninstall -y "${THUNDER_PACKGE_NAME}"
poetry "${ACTION}"
