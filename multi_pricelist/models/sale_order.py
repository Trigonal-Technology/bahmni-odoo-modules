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
from odoo import models
import logging
_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_update_prices(self):
        """Overriding the action_update_prices to clear the applied_pricelist_id
        in order lines so that the global pricelist is applied."""
        _logger.info("DEBUG: action_update_prices called")
        _logger.info("DEBUG: Order Lines: %s", self.order_line) 
        self.order_line.write({'applied_pricelist_id': False})
        _logger.info("DEBUG: Applied Pricelist ID cleared")
        super(SaleOrder, self).action_update_prices()
        _logger.info("DEBUG: action_update_prices completed")
        return True
