from odoo import fields, models


class StockReturnPicking(models.TransientModel):
    _inherit = "stock.return.picking"

    return_deadline = fields.Datetime(related="picking_id.return_deadline")
    return_expired = fields.Boolean(related="picking_id.return_expired")

    def _create_return(self):
        self.picking_id._check_return_allowed()
        return super()._create_return()
