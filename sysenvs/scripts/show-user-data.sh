#!/usr/bin/env bash
# Enable bash's unofficial strict mode
GITROOT=$(git rev-parse --show-toplevel)
# shellcheck disable=SC1090,SC1091
. "${GITROOT}"/scripts/lib/strict-mode
# shellcheck disable=SC1090,SC1091
. "${GITROOT}"/scripts/lib/utils
strictMode

THIS_SCRIPT=$(basename "${0}")
PADDING=$(printf %-${#THIS_SCRIPT}s " ")

function usage () {
  echo "Usage:"
  echo "${THIS_SCRIPT} -s, --stack-name <Pulumi stack name. Examples: k8s-agents, k8s-controllers. REQUIRED>"
  echo "${PADDING} -f, --first <Use this flag to pick the first Auto Scaling Group>"
  echo
  echo "Print base64 decoded and gunzip decompressed user-data for a given stack"
  exit 1
}

# Ensure dependencies are present
if ! command -v aws &> /dev/null || ! command -v git &> /dev/null || ! command -v jq &> /dev/null || ! command -v base64 &> /dev/null; then
  msg_fatal "[-] Dependencies unmet. Please verify that the following are installed and in the PATH: aws, base64, git, jq. Check README for requirements"
fi

FIRST='no'
while [[ $# -gt 0 ]]; do
  case "${1}" in
    -f|--first)
      FIRST='yes'
      shift # past argument
      ;;
    -s|--stack-name)
      STACK_NAME="${2}"
      shift # past argument
      shift # past value
      ;;
    -*)
      echo "Unknown option ${1}"
      usage
      ;;
  esac
done

if [[ -z ${STACK_NAME:-""} ]] ; then
  usage
fi

# Create temp directory
TMP_DIR="$(create_temp_dir "${THIS_SCRIPT}")"
function cleanup() {
  echo "Deleting ${TMP_DIR}"
  rm -rf "${TMP_DIR}"
}
# Make sure cleanup runs even if this script fails
trap cleanup EXIT


ASG_FILE="$(select_asg "${STACK_NAME}" "${TMP_DIR}" "${FIRST}")"

get_user_data "${ASG_FILE}" "${TMP_DIR}"
