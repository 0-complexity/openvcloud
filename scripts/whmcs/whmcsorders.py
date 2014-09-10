import requests
import hashlib

from settings import authenticationparams, WHMCS_API_ENDPOINT


def _call_whmcs_api(requestparams):
    actualrequestparams = dict()
    actualrequestparams.update(requestparams)
    actualrequestparams.update(authenticationparams)
    response = requests.post(WHMCS_API_ENDPOINT, data=actualrequestparams)
    return response

def add_order(userId, productId, name, cloudbrokerId):
    
    request_params = dict(

                action = 'addorder',
                name=name,
                pid = productId,
                clientid = userId,
                billingcycle = 'monthly',
                paymentmethod = 'paypal',
                customfields = [cloudbrokerId],
                noemail = True,
                skipvalidation= True

                )
    
    response = _call_whmcs_api(request_params)
    return response.ok


def list_orders():
    
    request_params = dict(
                action = 'getorders',
                limitnum = 10000000,
                responsetype = 'json'
                )

    response = _call_whmcs_api(request_params)
    if response.ok:
        orders = response.json()
        if orders['numreturned'] > 0:
            return orders['orders']
        return []
    else:
      raise
  
def delete_order(orderId):
    request_params = dict(
                action = 'deleteorder',
                orderid=orderId,
                responsetype = 'json'
                )
    
    response = _call_whmcs_api(request_params)
    return response.ok
