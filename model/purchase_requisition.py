from odoo import fields, models, api, _
from odoo.exceptions import UserError, AccessError
import logging
_logger = logging.getLogger(__name__)

class RFQ(models.Model):
    _inherit="purchase.order"

    pr_reference=fields.Char('PR Reference')


class PurchaseRequisition(models.Model):
    _name = "purchase.requisition"
    _description = "Purchase Requisition"
    _inherit = ['mail.thread', 'mail.activity.mixin']  

    name = fields.Char(string="Name", readonly=True, copy=False, default='/', tracking=True)

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('purchase.requisition') or '/'
        return super(PurchaseRequisition, self).create(vals)

    vendor_id = fields.Many2one('res.partner', string="Prefered Vendor", tracking=True, required=True)
    employee_name = fields.Char(string="Employee Name", compute="_compute_employee_name", store=True, tracking=True)
    department_id = fields.Many2one('hr.department', string="Department", compute="_compute_department", store=True, tracking=True)
    requisition_date = fields.Datetime(string="Requisition Date", default=fields.Datetime.now, tracking=True)
    requisition_deadline = fields.Datetime(string="Requisition Deadline", tracking=True)
    requisition_line_ids = fields.One2many('purchase.requisition.line', 'requisition_id', string="Requisition Lines", tracking=True)

    stage = fields.Selection([
        ('new', 'New'),
        ('waiting_approval', 'Waiting for Approval'),
        ('approved', 'Approved'),
        ('rfq_created', 'RFQ Created'),
    ], string="Stage", default='new', tracking=True)

    product_summary = fields.Char(string="Products", compute="_compute_product_summary", store=True, tracking=True)
    total_quantity = fields.Float(string="Total Quantity", compute="_compute_total_quantity", store=True, tracking=True)
    total_onhand_qty = fields.Float(string="Total On-hand Qty", compute="_compute_total_onhand_qty", store=True, tracking=True)

    @api.depends('create_uid')
    def _compute_employee_name(self):
        for rec in self:
            rec.employee_name = rec.create_uid.name  

    @api.depends('create_uid')
    def _compute_department(self):
        for rec in self:
            employee = rec.env['hr.employee'].search([('user_id', '=', rec.create_uid.id)], limit=1)
            rec.department_id = employee.department_id.id if employee else False

    @api.depends('requisition_line_ids.product_id')
    def _compute_product_summary(self):
        for rec in self:
            rec.product_summary = ', '.join(rec.requisition_line_ids.mapped('product_id.display_name')) if rec.requisition_line_ids else "No Products"

    @api.depends('requisition_line_ids.quantity')
    def _compute_total_quantity(self):
        for rec in self:
            rec.total_quantity = sum(rec.requisition_line_ids.mapped('quantity'))

    @api.depends('requisition_line_ids.onhand_qty')
    def _compute_total_onhand_qty(self):
        for rec in self:
            rec.total_onhand_qty = sum(rec.requisition_line_ids.mapped('onhand_qty'))

    def action_submit(self):
        self.message_post(body="Purchase Requisition submitted for approval.")
        self.write({'stage': 'waiting_approval'})

    def action_approve(self):
        if not self.env.user.has_group('base.group_system'):  
            raise AccessError(_("Only administrators can approve Purchase Requisitions."))
        self.message_post(body="Purchase Requisition approved.")
        self.write({'stage': 'approved'})

    def action_create_po(self):
        if self.stage != 'approved':
            raise UserError(_("You cannot create a Purchase Order unless the requisition is approved."))

        if not self.vendor_id:
            raise UserError(_("Please select a vendor before creating a Purchase Order."))

        purchase_order = self.env['purchase.order'].create({
            'partner_id': self.vendor_id.id,
            'pr_reference': self.name,
            'order_line': [(0, 0, {
                'product_id': line.product_id.id,
                'name': line.description,
                'product_qty': line.quantity,
                'price_unit': line.product_id.standard_price,
                'date_planned': self.requisition_date,
            }) for line in self.requisition_line_ids],
        })
        
        self.message_post(body="Request for Quotation (RFQ) created successfully.")
        self.write({'stage': 'rfq_created'})

    

    def action_open_rfq(self):
        self.ensure_one()
        rfqs = self.env['purchase.order'].search([('pr_reference', '=', self.name)])

        if not rfqs:
            raise UserError(_("No RFQ found for this Purchase Requisition."))

        return {
            'type': 'ir.actions.act_window',
            'name': 'Request for Quotation',
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', rfqs.ids)],
            'context': {'create': False},
        }

class PurchaseRequisitionLine(models.Model):
    _name = "purchase.requisition.line"
    _description = "Purchase Requisition Line"

    requisition_id = fields.Many2one('purchase.requisition', string="Requisition", required=True, ondelete="cascade", tracking=True)
    product_id = fields.Many2one('product.product', string="Product", required=True, tracking=True)
    description = fields.Char(string="Description", tracking=True)
    quantity = fields.Float(string="Quantity", required=True, tracking=True)
    onhand_qty = fields.Float(string="On-hand Qty", compute="_compute_onhand_qty", store=True, tracking=True)

    @api.depends('product_id')
    def _compute_onhand_qty(self):
        for rec in self:
            rec.onhand_qty = rec.product_id.qty_available if rec.product_id else 0

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for rec in self:
            if rec.product_id:
                rec.description = rec.product_id.display_name
