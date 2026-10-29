from datetime import datetime

from odoo.exceptions import UserError
from odoo.tests import Form, tagged
from odoo.addons.sale.tests.common import SaleCommon


@tagged("post_install", "-at_install")
class TestNaticiudadReturns(SaleCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company.return_days = 15
        cls.company.pickup_days = 2
        cls.product = cls.env["product.product"].create(
            {"name": "Tarta", "is_storable": True, "list_price": 100.0, "taxes_id": False}
        )
        cls.env["stock.quant"]._update_available_quantity(
            cls.product, cls.env.ref("stock.stock_location_stock"), 10
        )
        cls.order = cls.env["sale.order"].create({
            "partner_id": cls.partner.id,
            "order_line": [(0, 0, {"product_id": cls.product.id, "product_uom_qty": 2})],
        })
        cls.order.action_confirm()
        cls.delivery = cls.order.picking_ids
        cls.delivery.move_ids.quantity = 2
        cls.delivery.button_validate()

    def _return(self, picking=None):
        picking = picking or self.delivery
        wiz = Form(self.env["stock.return.picking"].with_context(
            active_id=picking.id, active_model="stock.picking")).save()
        wiz.product_return_moves.quantity = 1
        return wiz

    def _set_done(self, date):
        self.delivery.date_done = date
        self.env.flush_all()
        self.delivery.invalidate_recordset()

    def test_deadline_skips_weekends(self):
        # Viernes 2024-03-01: 15 laborables -> viernes 2024-03-22 (sin festivos en el calendario por defecto)
        self._set_done(datetime(2024, 3, 1, 10, 0))
        deadline = self.delivery.return_deadline
        self.assertEqual(deadline.date().isoformat(), "2024-03-22")
        self.assertGreaterEqual(deadline.hour, 21)  # final del día (hora de Madrid)

    def test_expired_return_blocked_and_override(self):
        self._set_done(datetime(2024, 3, 1, 10, 0))
        self.assertTrue(self.delivery.return_expired)
        with self.assertRaises(UserError):
            self._return().action_create_returns()
        manager = self.env["res.users"].create({
            "name": "Resp", "login": "resp_dev",
            "group_ids": [(6, 0, [self.env.ref("naticiudad_returns.group_return_override").id])],
        })
        self._return().with_user(manager).action_create_returns()

    def test_in_time_return_creates_pickup_deadline_and_voucher(self):
        self.assertFalse(self.delivery.return_expired)
        ret = self.env["stock.picking"].browse(self._return().action_create_returns()["res_id"])
        self.assertTrue(ret.is_customer_return)
        self.assertTrue(ret.pickup_deadline)
        ret.move_ids.quantity = 1
        ret.button_validate()
        voucher = ret.return_voucher_id
        self.assertTrue(voucher)
        self.assertAlmostEqual(voucher.points, 100.0)
        self.assertEqual(voucher.partner_id, self.partner)

    def test_no_voucher_when_disabled(self):
        self.company.return_voucher_auto = False
        ret = self.env["stock.picking"].browse(self._return().action_create_returns()["res_id"])
        ret.move_ids.quantity = 1
        ret.button_validate()
        self.assertFalse(ret.return_voucher_id)

    def test_overdue_pickup_cron_schedules_activity_once(self):
        ret = self.env["stock.picking"].browse(self._return().action_create_returns()["res_id"])
        ret.pickup_deadline = datetime(2024, 1, 1)
        self.env["stock.picking"]._cron_check_overdue_pickups()
        self.env["stock.picking"]._cron_check_overdue_pickups()
        self.assertTrue(ret.pickup_alert_sent)
        self.assertEqual(len(ret.activity_ids), 1)
