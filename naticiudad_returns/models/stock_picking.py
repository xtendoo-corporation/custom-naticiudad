from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    return_deadline = fields.Datetime(
        string="Límite de devolución",
        compute="_compute_return_deadline",
        store=True,
        help="Último momento en que el cliente puede devolver esta entrega.",
    )
    return_expired = fields.Boolean(
        string="Plazo de devolución vencido", compute="_compute_return_expired"
    )
    is_customer_return = fields.Boolean(
        string="Devolución de cliente", compute="_compute_is_customer_return", store=True
    )
    pickup_deadline = fields.Datetime(string="Límite de recogida", copy=False, readonly=True)
    pickup_alert_sent = fields.Boolean(copy=False)
    return_voucher_id = fields.Many2one(
        "loyalty.card", string="Vale de devolución", copy=False, readonly=True
    )

    @api.depends("date_done", "state", "picking_type_code", "company_id.return_days",
                 "company_id.return_calendar_id", "company_id.resource_calendar_id")
    def _compute_return_deadline(self):
        for picking in self:
            deadline = False
            if (
                picking.state == "done"
                and picking.picking_type_code == "outgoing"
                and picking.date_done
                and picking.company_id.return_days
            ):
                deadline = self.env["res.company"]._naticiudad_add_workdays(
                    picking.company_id, picking.date_done, picking.company_id.return_days
                )
            picking.return_deadline = deadline

    @api.depends("return_deadline")
    def _compute_return_expired(self):
        now = fields.Datetime.now()
        for picking in self:
            picking.return_expired = bool(picking.return_deadline and now > picking.return_deadline)

    @api.depends("return_id.picking_type_code", "picking_type_code")
    def _compute_is_customer_return(self):
        for picking in self:
            picking.is_customer_return = (
                picking.picking_type_code == "incoming"
                and picking.return_id.picking_type_code == "outgoing"
            )

    # ------------------------------------------------------------------
    # Plazo de devolución
    # ------------------------------------------------------------------
    def _check_return_allowed(self):
        if self.env.user.has_group("naticiudad_returns.group_return_override"):
            return
        for picking in self:
            if picking.return_expired:
                raise UserError(_(
                    "El plazo de devolución de %(name)s venció el %(date)s. "
                    "Solo un responsable de devoluciones puede aceptarla.",
                    name=picking.name,
                    date=fields.Datetime.context_timestamp(picking, picking.return_deadline)
                    .strftime("%d/%m/%Y %H:%M"),
                ))

    # ------------------------------------------------------------------
    # Recogida en 48 h
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        pickings = super().create(vals_list)
        for picking in pickings.filtered("is_customer_return"):
            days = picking.company_id.pickup_days
            if days:
                picking.pickup_deadline = self.env["res.company"]._naticiudad_add_workdays(
                    picking.company_id, fields.Datetime.now(), days
                )
        return pickings

    @api.model
    def _cron_check_overdue_pickups(self):
        overdue = self.search([
            ("is_customer_return", "=", True),
            ("state", "not in", ("done", "cancel")),
            ("pickup_deadline", "<", fields.Datetime.now()),
            ("pickup_alert_sent", "=", False),
        ])
        for picking in overdue:
            picking.activity_schedule(
                "mail.mail_activity_data_todo",
                summary=_("Recogida fuera de plazo"),
                note=_("La recogida de %(name)s no se completó antes de %(date)s.",
                       name=picking.name, date=picking.pickup_deadline),
                user_id=(picking.user_id or picking.create_uid).id,
            )
            picking.pickup_alert_sent = True

    # ------------------------------------------------------------------
    # Vale automático
    # ------------------------------------------------------------------
    def _action_done(self):
        res = super()._action_done()
        self.filtered("is_customer_return")._create_return_voucher()
        return res

    def _get_return_voucher_amount(self):
        self.ensure_one()
        amount = 0.0
        for move in self.move_ids.filtered(lambda m: m.state == "done"):
            sale_line = move.origin_returned_move_id.sale_line_id
            if not sale_line or not sale_line.product_uom_qty:
                continue
            unit_total = sale_line.price_total / sale_line.product_uom_qty
            qty = move.product_uom._compute_quantity(move.quantity, sale_line.product_uom_id)
            amount += unit_total * qty
        return amount

    def _create_return_voucher(self):
        for picking in self:
            company = picking.company_id
            program = company.return_voucher_program_id
            if (
                not company.return_voucher_auto
                or not program
                or picking.return_voucher_id
                or not picking.partner_id
            ):
                continue
            amount = picking._get_return_voucher_amount()
            if picking.sale_id.currency_id != program.currency_id:
                amount = picking.sale_id.currency_id._convert(
                    amount, program.currency_id, company, fields.Date.context_today(picking)
                )
            if program.currency_id.is_zero(amount):
                continue
            validity = company.return_voucher_validity_days
            card = self.env["loyalty.card"].create({
                "program_id": program.id,
                "partner_id": picking.partner_id.commercial_partner_id.id,
                "points": amount,
                "expiration_date": fields.Date.context_today(picking) + timedelta(days=validity)
                if validity else False,
            })
            picking.return_voucher_id = card
            picking.message_post(body=_(
                "Vale de devolución %(code)s generado por %(amount)s.",
                code=card.code, amount=program.currency_id.format(amount),
            ))
