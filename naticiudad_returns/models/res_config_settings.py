from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    return_days = fields.Integer(related="company_id.return_days", readonly=False)
    pickup_days = fields.Integer(related="company_id.pickup_days", readonly=False)
    return_calendar_id = fields.Many2one(related="company_id.return_calendar_id", readonly=False)
    return_voucher_auto = fields.Boolean(related="company_id.return_voucher_auto", readonly=False)
    return_voucher_program_id = fields.Many2one(
        related="company_id.return_voucher_program_id", readonly=False
    )
    return_voucher_validity_days = fields.Integer(
        related="company_id.return_voucher_validity_days", readonly=False
    )
