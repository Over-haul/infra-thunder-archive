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
  echo "${PADDING} -r, --replace <Use this flag to indicate instances should be replaced. if NOT used desired capacity will be decreased>"
  echo "${PADDING} -y, --yes <Use this flag to answer 'Yes' to all questions>"
  echo "${PADDING} --no-k8s-check <Use this flag to NOT check if k8s is available>"
  echo
  echo "Retire instances NOT using current Launch Template version"
  exit 1
}

# Ensure dependencies are present
if ! command -v aws &> /dev/null || ! command -v git &> /dev/null || ! command -v jq &> /dev/null || ! command -v kubectl &> /dev/null; then
  msg_fatal "[-] Dependencies unmet. Please verify that the following are installed and in the PATH: aws, git, jq, kubectl. Check README for requirements"
fi

ACTION='terminate'
ASK='yes'
CHECK_K8S='yes'
while [[ $# -gt 0 ]]; do
  case "${1}" in
    --no-k8s-check)
      CHECK_K8S='no'
      shift # past argument
      ;;
    -r|--replace)
      ACTION='replace'
      shift # past argument
      ;;
    -s|--stack-name)
      STACK_NAME="${2}"
      shift # past argument
      shift # past value
      ;;
    -y|--yes)
      ASK='no'
      shift # past argument
      ;;
    -*)
      msg_error "Unknown option ${1}"
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

msg_info "I will ${ACTION} instance(s)"

# get all instances that are NOT on current Launch Template version
declare -a INSTANCES=()
while IFS= read -r i; do
  INSTANCES+=("${i}")
done < <(get_old_instances "${STACK_NAME}" "${TMP_DIR}")

# Exit if there are no out of date instances
if [[ ${#INSTANCES[@]} -eq 0 ]]; then
  msg_info 'bye bye!'
  exit 0
fi

# When working on k8s-controllers we limit the number of instances to 1
if [[ "${STACK_NAME}" =~ ^k8s-controllers.* ]]; then
  msg_info "Since you are working on stack ${STACK_NAME}"
  msg_info "I will only work on 1 instance"
  msg_info "Instance: $(get_instance_id "${INSTANCES[0]}")"
  INSTANCES=("${INSTANCES[0]}")
fi

# We assume Auto Scaling Groups can be used for other stacks than k8s
IS_K8S_AVAILABLE='no'
# We should only check if k8s is available when handling k8s stacks
if [[ "${STACK_NAME}" =~ ^k8s.* ]]; then
  IS_K8S_AVAILABLE="$(is_k8s_available "${CHECK_K8S}")"
  msg_info "Is kubernetes reachable? ${IS_K8S_AVAILABLE}"
fi

# Cordon all instances
if [[ "${IS_K8S_AVAILABLE}" == 'yes' ]]; then
  for instance in "${INSTANCES[@]}"; do
    cordon_or_drain_instance "${instance}" "${ASK}" 'cordon'
  done
fi

# Drain and terminate/replace instances 1 at a time
for instance in "${INSTANCES[@]}"; do
  retire_instance "${instance}" "${ACTION}" "${ASK}" "${IS_K8S_AVAILABLE}"
done
