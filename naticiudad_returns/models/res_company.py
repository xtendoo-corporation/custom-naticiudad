from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    return_days = fields.Integer(
        string="Plazo de devolución (días laborables)",
        default=15,
        help="Días laborables, desde la entrega al cliente, durante los que se admite una devolución. 0 = sin límite.",
    )
    pickup_days = fields.Integer(
        string="Plazo de recogida (días laborables)",
        default=2,
        help="Días laborables máximos para recoger una devolución al cliente (48 h = 2 días laborables). 0 = sin control.",
    )
    return_calendar_id = fields.Many2one(
        "resource.calendar",
        string="Calendario laborable",
        help="Calendario (jornada y festivos) con el que se cuentan los días laborables. "
        "Por defecto, el calendario de la compañía.",
    )
    return_voucher_auto = fields.Boolean(
        string="Vale automático en devoluciones",
        default=True,
    )
    return_voucher_program_id = fields.Many2one(
        "loyalty.program",
        string="Programa del vale",
        domain=[("program_type", "in", ("ewallet", "gift_card"))],
        default=lambda self: self.env.ref(
            "naticiudad_returns.loyalty_program_return_voucher", raise_if_not_found=False
        ),
    )
    return_voucher_validity_days = fields.Integer(
        string="Validez del vale (días)",
        default=0,
        help="0 = el vale no caduca.",
    )

    @api.model
    def _naticiudad_add_workdays(self, company, start, days):
        """Fecha límite (fin del día) tras `days` días laborables desde `start` (UTC naive).

        El día de `start` no cuenta: el primer día laborable es el siguiente.
        """
        calendar = company.return_calendar_id or company.resource_calendar_id
        if not calendar or not days:
            return False
        tz = pytz.timezone(calendar.tz or "UTC")
        local_start = pytz.utc.localize(start).astimezone(tz)
        next_midnight = tz.localize(
            datetime.combine(local_start.date() + timedelta(days=1), time.min)
        )
        end = calendar.plan_days(days, next_midnight, compute_leaves=True)
        if not end:
            return False
        # El plazo vence al final del último día laborable, no al cierre del primer turno.
        end_of_day = tz.localize(datetime.combine(end.astimezone(tz).date(), time(23, 59, 59)))
        return end_of_day.astimezone(pytz.utc).replace(tzinfo=None)
