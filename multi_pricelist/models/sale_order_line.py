# -*- coding: utf-8 -*-
################################################################################
#
#    Trigonal Technology
#    Copyright (C) 2024-TODAY Trigonal Technology(<https://www.trigonaltechnology.com>).
#    Author: Bhagyadev KP (odoo@trigonaltechnology.com)
#
#    This program is free software: you can modify
#    it under the terms of the GNU Affero General Public License (AGPL) as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
################################################################################
from datetime import datetime
from odoo import fields, models, _, api
from odoo.exceptions import UserError



import logging
_logger = logging.getLogger(__name__)

class SaleOrderLine(models.Model):
    """Inherits Sale order line to add the functions for checking the
    visibility of the pricelists in order lines and also apply the
    pricelist to order lines"""
    _inherit = 'sale.order.line'

    pricelist_visibility = fields.Boolean(
        compute="_compute_pricelist_visibility", string="Pricelist Visible",
        help="Multi Pricelist enabled or not")
    applied_pricelist_id = fields.Many2one('product.pricelist',
                                           string="PriceList",
                                           help="Price lists that is applied to"
                                                "the order line.")

    @api.depends('product_id', 'product_uom', 'product_uom_qty')
    def _compute_price_unit(self):
        for line in self:
            # check if there is already invoiced amount. if so, the price shouldn't change as it might have been
            # manually edited
            if line.qty_invoiced > 0:
                continue
            if not line.product_uom or not line.product_id or not line.order_id.pricelist_id:
                line.price_unit = 0.0
            else:
                price = line.with_company(line.company_id)._get_display_price()
                line.price_unit = line.product_id._get_tax_included_unit_price(
                    line.company_id,
                    line.order_id.currency_id,
                    line.order_id.date_order,
                    'sale',
                    fiscal_position=line.order_id.fiscal_position_id,
                    product_price_unit=price,
                    product_currency=line.currency_id
                )

    def _get_pricelist_price(self):
        # Overriding the _get_pricelist_price method to apply multiple pricelist
        self.ensure_one()
        self.product_id.ensure_one()
        
        pricelist = self.applied_pricelist_id or self.order_id.pricelist_id
        
        _logger.info("DEBUG: _get_pricelist_price for Product: %s (ID: %s)", self.product_id.display_name, self.product_id.id)
        _logger.info("DEBUG: Applied Pricelist ID: %s, Global Pricelist ID: %s -> Using: %s", 
                     self.applied_pricelist_id.id, self.order_id.pricelist_id.id, pricelist.name)

        if pricelist:
            product = self.product_id
            quantity = self.product_uom_qty or 1.0
            uom = self.product_uom
            date = self.order_id.date_order
            
            # Get the pricelist item rule
            pricelist_item_id = pricelist._get_product_rule(
                product,
                quantity=quantity,
                uom=uom,
                date=date,
            )
            _logger.info("DEBUG: Found Pricelist Rule ID: %s", pricelist_item_id)
            
            if pricelist_item_id:
                pricelist_item = self.env['product.pricelist.item'].browse(pricelist_item_id)
                # Compute price using the pricelist item
                price = pricelist_item._compute_price(
                    product=product.with_context(
                        **self._get_product_price_context()),
                    quantity=quantity,
                    uom=uom,
                    date=date,
                    currency=self.currency_id,
                )
                _logger.info("DEBUG: Computed Price matches Rule: %s", price)
                return price
            else:
                # Fallback to standard price if no rule found
                _logger.info("DEBUG: No rule found. Fallback to List Price: %s", product.list_price)
                return product.list_price
        else:
            _logger.info("DEBUG: No Pricelist found. Fallback to List Price: %s", self.product_id.list_price)
            return self.product_id.list_price

    def apply_pricelist(self):
        """This function will help to select all the pricelists
        for a product in order line and apply it"""
        for rec in self:
            date_today = datetime.today().date()
            # find the matching price list for a product
            price_ids = self.env['product.pricelist.item'].search(
                ['|', '|', ('product_tmpl_id', '=', False),
                 ('categ_id', '=', rec.product_id.categ_id.id),
                 ('product_tmpl_id', '=', rec.product_id.product_tmpl_id.id),
                 ('min_quantity', '<=', rec.product_uom_qty),'|',
                 ('date_start', '<=', date_today),
                 ('date_start', '=', False), '|',
                 ('date_end', '>=', date_today),
                 ('date_end', '=', False),
                 ])
            variant_ids = self.env['product.pricelist.item'].search(
                [
                    ('product_id', '=', rec.product_id.id),
                    ('min_quantity', '<=', rec.product_uom_qty),
                    '|', ('date_start', '<=', date_today),
                    ('date_start', '=', False), '|',
                    ('date_end', '>=', date_today),
                    ('date_end', '=', False),
                ])
            combined_ids = price_ids + variant_ids
            if combined_ids:
                pricelist_wizard = self.env['pricelist.product'].create({
                    'order_line_id': rec.id,
                    'line_ids': [(0, 0, {
                        'pricelist_id': price.pricelist_id.id,
                        'product_id': rec.product_id.id,
                        'unit_price': self.unit_price(price),
                        'unit_cost': rec.product_id.standard_price,
                        'uom_id': rec.product_id.uom_id.id
                    }) for price in combined_ids],
                })
            else:
                raise UserError(_(
                    "No price list is configured for this product!"))
        return {
            'type': 'ir.actions.act_window',
            'target': 'new',
            'name': 'Select Pricelist',
            'view_mode': 'form',
            'view_id': self.env.ref(
                "multi_pricelist.pricelist_wizard_view_form", False).id,
            'res_model': 'pricelist.product',
            'res_id': pricelist_wizard.id,
        }

    def _compute_pricelist_visibility(self):
        """ Computes pricelist_visibility by checking the config parameter."""
        for rec in self:
            rec.pricelist_visibility = self.env[
                'ir.config_parameter'].sudo().get_param(
                'multi_pricelist.multi_pricelist')
            if rec.order_id.state in ['sale', 'done', 'cancel']:
                rec.pricelist_visibility = False

    def unit_price(self, price):
        """Compute the unit price of the product according to the
        price_list_item"""
        if price.compute_price == 'fixed':
            unt_price = price.fixed_price
        elif price.compute_price == 'percentage' and price.percent_price != 0:
            unt_price = self.product_id.list_price * (
                    1 - price.percent_price / 100)
        elif price.compute_price == 'formula' and price.base == 'list_price':
            unt_price = (self.product_id.list_price * (
                    1 - price.price_discount / 100) + price.price_surcharge)
            if price.price_min_margin or price.price_max_margin:
                if (unt_price < price.price_min_margin +
                        self.product_id.list_price):
                    unt_price = (price.price_min_margin +
                                 self.product_id.list_price)
                elif (unt_price > price.price_max_margin +
                      self.product_id.list_price):
                    unt_price = (price.price_max_margin +
                                 self.product_id.list_price)
                else:
                    unt_price = unt_price
        elif price.compute_price == 'formula' and price.base == 'standard_price':
            unt_price = (self.product_id.standard_price * (
                    1 - price.price_discount / 100) + price.price_surcharge)
            if price.price_min_margin or price.price_max_margin:
                if (unt_price < price.price_min_margin +
                        self.product_id.list_price):
                    unt_price = (price.price_min_margin +
                                 self.product_id.list_price)
                elif (unt_price > price.price_max_margin +
                      self.product_id.list_price):
                    unt_price = (price.price_max_margin +
                                 self.product_id.list_price)
                else:
                    unt_price = unt_price
        elif price.compute_price == 'formula' and price.base == 'pricelist':
            unt_price = (self.unit_price(price.base_pricelist_id.item_ids) * (
                    1 - price.price_discount / 100) + price.price_surcharge)
            if price.price_min_margin or price.price_max_margin:
                if (unt_price < price.price_min_margin +
                        self.product_id.list_price):
                    unt_price = (price.price_min_margin +
                                 self.product_id.list_price)
                elif (unt_price > price.price_max_margin +
                      self.product_id.list_price):
                    unt_price = (price.price_max_margin +
                                 self.product_id.list_price)
                else:
                    unt_price = unt_price
        else:
            unt_price = self.product_id.list_price
        return unt_price
