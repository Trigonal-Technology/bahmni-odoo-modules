
import xmlrpc.client
import sys

# Configuration
EXT_DB_NAME = 'odoo'
EXT_USER = 'admin'
EXT_PASS = 'admin'
URL = "http://localhost:8069"

def run_test():
    print(f"Connecting to {URL}...")
    common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(URL))
    uid = common.authenticate(EXT_DB_NAME, EXT_USER, EXT_PASS, {})
    
    if not uid:
        print("Authentication failed!")
        sys.exit(1)
    
    print(f"Authenticated with UID: {uid}")
    models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(URL), allow_none=True)
    
    # 1. Create Product 'Orange'
    print("Creating product 'Orange'...")
    product_id = models.execute_kw(EXT_DB_NAME, uid, EXT_PASS, 'product.product', 'create', [{
        'name': 'Orange',
        'type': 'product',  # Storable
        'list_price': 10.0, # Base price
    }])
    print(f"Product 'Orange' created with ID: {product_id}")
    
    # 2. Setup Pricelists
    # Public Pricelist (assuming it exists or creating one)
    public_pl_ids = models.execute_kw(EXT_DB_NAME, uid, EXT_PASS, 'product.pricelist', 'search', [[['name', '=', 'Public Pricelist']]])
    if public_pl_ids:
        public_pl_id = public_pl_ids[0]
    else:
        public_pl_id = models.execute_kw(EXT_DB_NAME, uid, EXT_PASS, 'product.pricelist', 'create', [{'name': 'Public Pricelist'}])
    
    print(f"Using Public Pricelist ID: {public_pl_id}")
    
    # OPD Pricelist
    opd_pl_ids = models.execute_kw(EXT_DB_NAME, uid, EXT_PASS, 'product.pricelist', 'search', [[['name', '=', 'OPD']]])
    if opd_pl_ids:
        opd_pl_id = opd_pl_ids[0]
    else:
        opd_pl_id = models.execute_kw(EXT_DB_NAME, uid, EXT_PASS, 'product.pricelist', 'create', [{'name': 'OPD'}])
        
    print(f"Using OPD Pricelist ID: {opd_pl_id}")
    
    # Get Template ID
    product_data = models.execute_kw(EXT_DB_NAME, uid, EXT_PASS, 'product.product', 'read', [[product_id], ['product_tmpl_id']])
    product_tmpl_id = product_data[0]['product_tmpl_id'][0]
    print(f"Product Template ID: {product_tmpl_id}")

    # 3. Create Pricelist Items (on Template)
    # Public: 59
    models.execute_kw(EXT_DB_NAME, uid, EXT_PASS, 'product.pricelist.item', 'create', [{
        'pricelist_id': public_pl_id,
        'applied_on': '1_product',
        'product_tmpl_id': product_tmpl_id,
        'fixed_price': 59.0,
        'compute_price': 'fixed'
    }])
    
    # OPD: 99
    models.execute_kw(EXT_DB_NAME, uid, EXT_PASS, 'product.pricelist.item', 'create', [{
        'pricelist_id': opd_pl_id,
        'applied_on': '1_product',
        'product_tmpl_id': product_tmpl_id,
        'fixed_price': 99.0,
        'compute_price': 'fixed'
    }])
    
    print("Pricelist items created: Public=59, OPD=99")
    
    # Find a Shop (Bahmni specific)
    shop_ids = models.execute_kw(EXT_DB_NAME, uid, EXT_PASS, 'sale.shop', 'search', [[]])
    shop_id = shop_ids[0] if shop_ids else False
    print(f"Using Shop ID: {shop_id}")

    # 4. Create Sale Order with Public Pricelist
    print("Creating Sale Order with Public Pricelist...")
    order_vals = {
        'partner_id': 3, 
        'pricelist_id': public_pl_id,
    }
    if shop_id:
        order_vals['shop_id'] = shop_id
        
    order_id = models.execute_kw(EXT_DB_NAME, uid, EXT_PASS, 'sale.order', 'create', [order_vals])
    
    # Add Order Line
    line_id = models.execute_kw(EXT_DB_NAME, uid, EXT_PASS, 'sale.order.line', 'create', [{
        'order_id': order_id,
        'product_id': product_id,
        'product_uom_qty': 1,
    }])
    
    # Verify Initial Price
    line_data = models.execute_kw(EXT_DB_NAME, uid, EXT_PASS, 'sale.order.line', 'read', [[line_id], ['price_unit']])
    print(f"Initial Price (Public): {line_data[0]['price_unit']}")
    
    if line_data[0]['price_unit'] != 59.0:
        print("ERROR: Initial price is not 59.0!")
    
    # 5. Switch to OPD Pricelist and Update Prices
    print("Switching to OPD Pricelist...")
    models.execute_kw(EXT_DB_NAME, uid, EXT_PASS, 'sale.order', 'write', [[order_id], {'pricelist_id': opd_pl_id}])
    
    print("Calling action_update_prices...")
    # This calls the method we overrode
    models.execute_kw(EXT_DB_NAME, uid, EXT_PASS, 'sale.order', 'action_update_prices', [[order_id]])
    
    # 6. Verify Updated Price
    line_data_new = models.execute_kw(EXT_DB_NAME, uid, EXT_PASS, 'sale.order.line', 'read', [[line_id], ['price_unit', 'applied_pricelist_id']])
    new_price = line_data_new[0]['price_unit']
    applied_pl = line_data_new[0]['applied_pricelist_id']
    
    print(f"New Price (OPD): {new_price}")
    print(f"Applied Pricelist ID on line: {applied_pl}")
    
    if new_price == 99.0:
        print("SUCCESS: Price updated correctly to 99.0!")
    else:
        print("FAILURE: Price did not update to 99.0")
        
    if not applied_pl:
        print("SUCCESS: Line specific pricelist was cleared.")
    else:
        print("FAILURE: Line specific pricelist was NOT cleared.")

if __name__ == '__main__':
    # Ensure partner exists for SO
    # Just a small helper to get a partner
    try:
        run_test()
    except Exception as e:
        print(f"An error occurred: {e}")
