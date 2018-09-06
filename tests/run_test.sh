set -o pipefail

usage(){
    echo "Usage"
    echo "options:"
    echo "  --testsuite: testsuite name"
    echo "  --testsuite: tests path"
}

while true; do
  case "$1" in
    --testsuite) TESTSUITE=${2}; shift ;;
    --path) TESTS_PATH=${2}; shift ;;
    --help) usage shift ;;
    * ) break ;;
  esac
  shift
done

protocol=${protocol:-https}
CI_JOB_NAME=${CI_JOB_NAME:-${TESTSUITE}}
CI_PIPELINE_ID=${CI_PIPELINE_ID:-'0'}
LOGFILE="/tmp/${CI_JOB_NAME}_${CI_PIPELINE_ID}.log"

if [[ ${TESTSUITE} == "acl" ]] || [[ ${TESTSUITE} == "ovc" ]]; then

    export PYTHONPATH=/opt/jumpscale7/lib:/opt/jumpscale7/lib/lib-dynload/:/opt/jumpscale7/bin:/opt/jumpscale7/lib/python.zip:/opt/jumpscale7/lib/plat-x86_64-linux-gnu
    nosetests-2.7 -s -v --logging-level=WARNING ${TESTS_PATH} --tc-file config.ini --tc=main.url:${url} --tc=main.environment:${environment} --tc=main.protocol:${protocol} 2>&1 | tee ${LOGFILE}

elif [[ ${TESTSUITE} == "portal" ]]; then

    cd ovc_master_hosted/Portal
    export PYTHONPATH=./
    su - test -c "cd /opt/code/github/0-complexity/openvcloud/tests/ovc_master_hosted/Portal;\
    xvfb-run -a nosetests -s -v --logging-level=WARNING ${TESTS_PATH} --tc-file config.ini --tc=main.env:${url} \
    --tc=main.location:${environment} --tc=main.admin:${admin} --tc=main.passwd:${passwd} \
    --tc=main.secret:${secret} --tc=main.browser:chrome 2>&1 | tee ${LOGFILE}" 

else
    echo "Invalid testsuite name"
fi
