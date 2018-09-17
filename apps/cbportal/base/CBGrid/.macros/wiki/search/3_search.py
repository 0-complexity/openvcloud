

import math
import time
from cloudbrokerlib.cloudbroker import db

# number of results of each category on one page
# of search results
RESULTS_PER_PAGE = 10

# default page number
DEFAULT_PAGE_NR = 1

# range of pages shown in page controls
PAGE_RANGE = 5


FILTERS = {
    "account": {
        "url": "/CBGrid/account?id=",
        "search_fields": ["name"],
        "result_fields": ["id", "name", "status", "creationTime", "acl.userGroupId"],
        "namespace": "cloudbroker",
        "label": "Account",
    },
    "cloudspace": {
        "url": "/CBGrid/cloud%20space?id=",
        "search_fields": ["name", "externalnetworkip"],
        "result_fields": [
            "id",
            "name",
            "status",
            "accountId",
            "creationTime",
            "networkId",
            "externalnetworkip",
            "acl.userGroupId",
        ],
        "namespace": "cloudbroker",
        "label": "Cloud Space",
    },
    "vmachine": {
        "url": "/CBGrid/Virtual%20Machine?id=",
        "search_fields": ["name", "nics.ipAddress"],
        "result_fields": [
            "id",
            "name",
            "status",
            "nics.ipAddress",
            "stackId",
            "cloudspaceId",
        ],
        "namespace": "cloudbroker",
        "label": "Virtual Machine",
    },
    "image": {
        "url": "/CBGrid/image?id=",
        "search_fields": ["name", "type"],
        "result_fields": ["id", "name", "status", "type"],
        "namespace": "cloudbroker",
        "label": "Image",
    },
    "disk": {
        "url": "/CBGrid/disk?id=",
        "search_fields": ["name", "type"],
        "result_fields": ["id", "name", "status", "type"],
        "namespace": "cloudbroker",
        "label": "Disk",
    },
    "externalnetwork": {
        "url": "/CBGrid/External%20Network?networkid=",
        "search_fields": ["name", "ips"],
        "result_fields": ["id", "name", "ips"],
        "namespace": "cloudbroker",
        "label": "External Network",
    },
    "node": {
        "url": "/CBGrid/physicalnode?id=",
        "search_fields": ["name", "ipaddr"],
        "result_fields": ["id", "name", "status", "ipaddr"],
        "namespace": "system",
        "label": "Physical Node",
    },
    "user": {
        "url": "/CBGrid/user?id=",
        "search_fields": ["id"],
        "result_fields": ["id", "active", "creationTime", "groups"],
        "namespace": "system",
        "label": "User",
    },
}

CLICKABLE_FIELDS = {
    "cloudspaceId": FILTERS["cloudspace"]["url"],
    "accountId": FILTERS["account"]["url"],
    "stackId": "/CBGrid/stack?id=",
    "networkId": FILTERS["externalnetwork"]["url"],
    "userGroupId": FILTERS["user"]["url"],
}


class Filter(object):
    def __init__(self, name, dictionary, j):
        self.name = name
        self.data = dictionary

    def __getattr__(self, attr):
        return self.data[attr]

    @property
    def client(self):
        return getattr(getattr(db, self.namespace), self.name)


def search(j, query=None, filters=FILTERS.keys(), page_nr=1):
    """
    Implements search function in OVC

    :param request: search request containing a name/id or any object on OVC
    :param filter: filters for search
    :param page_nr: number of page, if None first page assumed.
            At most @RESULTS_PER_PAGE results for each category are listed in one page
    """

    if not filters:
        filters = FILTERS.keys()

    if isinstance(filters, str):
        filters = [filters]

    if page_nr < 1:
        page_nr = 1

    results = {}
    max_result_count = 0
    for fil in filters:
        queries, fields = [], []

        # search in ID only if query parsed as integer
        try:
            queries.append({"id": int(query)})
        except ValueError:
            pass

        filter_data = Filter(fil, FILTERS[fil], j)
        for field in filter_data.search_fields:
            queries.append({field: {"$regex": query, "$options": "i"}})
        for field in filter_data.result_fields:
            fields.append(field)
        request = {
            "$query": {"$or": queries, "status": {"$not": {"$eq": "DESTROYED"}}},
            "$fields": fields,
        }
        search_output = filter_data.client.search(
            request, start=(page_nr - 1) * RESULTS_PER_PAGE, size=RESULTS_PER_PAGE
        )
        ids = search_output[1:]
        if search_output[0] > max_result_count:
            max_result_count = search_output[0]
        if ids:
            results[fil] = ids

    total_page_count = int(math.ceil(max_result_count * 1.0 / RESULTS_PER_PAGE))
    return results, total_page_count


def search_format(result):
    """
    Format search results and add to @page

    :param page: page object
    :param result: search results given as dictionary
    """

    for ovc_object in result:
        for item in result[ovc_object]:

            def formating(input_dict):
                output = ""
                if isinstance(input_dict, dict):
                    for field in input_dict:
                        if "name" not in input_dict and field == "id":
                            # exclude field "id" from results of type "user". Can be distinguished
                            # by absence of field "name"
                            continue
                        formated_output = formating(input_dict[field])
                        if formated_output != "" or None:
                            if field == "creationTime":
                                formated_output = time.ctime(int(formated_output))
                            line = "<span class=search_result><b>{}:</b> {} </span>".format(
                                field, formated_output
                            )
                            if field in CLICKABLE_FIELDS:
                                line = "<a href={}{}>{}</a>".format(
                                    CLICKABLE_FIELDS[field], input_dict[field], line
                                )
                            output = "".join([output, line])
                elif isinstance(input_dict, list):
                    output = ""
                    for item in input_dict:
                        separator = ", " if item != input_dict[-1] else ""
                        line = "<span class=search_result background-color=green>{}{}</span>".format(
                            formating(item), separator
                        )
                        output = "".join([output, line])
                else:
                    return input_dict
                return output

            item["output"] = formating(item)


def main(j, args, params, tags, tasklet):
    params.result = (args.doc, args.doc)
    data = {}

    # get query
    query = args.requestContext.params.get("q")

    # get list of filters
    data["checked_filters"] = args.requestContext.params.get("filter") or []

    # get page number. "page" argument must parse to int
    try:
        page_nr = int(args.requestContext.params.get("page") or DEFAULT_PAGE_NR)
    except ValueError:
        page_nr = DEFAULT_PAGE_NR

    results = {}
    total_page_count = 1
    data["pages"] = []
    if query:
        results, total_page_count = search(j, query, data["checked_filters"], page_nr)
        if total_page_count > 1:
            # add pages controls
            pages_in_range = range(
                max(page_nr - PAGE_RANGE, 1),
                min(page_nr + PAGE_RANGE, total_page_count) + 1,
            )
            for page_id in pages_in_range:
                # page_class = "pages" if page_id != page_nr else "current_page"
                data["pages"].append(
                    {
                        "id": page_id,
                        "class": "pages" if page_id != page_nr else "current_page",
                    }
                )

    search_format(results)
    data["results"] = results
    data["FILTERS"] = FILTERS
    data["total_page_count"] = total_page_count
    args.doc.applyTemplate(data)

    return params


def match(j, args, params, tags, tasklet):
    return True

