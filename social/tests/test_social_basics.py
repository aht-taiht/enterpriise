# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta

from odoo import fields
from odoo.addons.social.tests import common
from odoo.addons.base.tests.test_ir_cron import CronMixinCase
from odoo.tests.common import users


class TestSocialBasics(common.SocialCase, CronMixinCase):
    def test_cron_triggers(self):
        """ When scheduling social posts, CRON triggers should be created to run the CRON sending
        the post as close to the time frame as possible. """

        scheduled_date = fields.Datetime.now() + timedelta(days=1)
        with self.capture_triggers('social.ir_cron_post_scheduled') as captured_triggers:
            social_post = self.env['social.post'].create({
                'account_ids': [(4, self.social_account.id)],
                'message': 'Test CRON triggers',
                'post_method': 'scheduled',
                'scheduled_date': scheduled_date
            })

        self.assertEqual(len(captured_triggers.records), 1)
        captured_trigger = captured_triggers.records[0]
        self.assertEqual(captured_trigger.call_at, scheduled_date)
        self.assertEqual(captured_trigger.cron_id, self.env.ref('social.ir_cron_post_scheduled'))

        # When updating the scheduled date, a new CRON trigger should be created with the new date.
        # Note that we intentionally do not remove / update the old trigger, as we would complicate
        # the code and it's not necessary (CRON triggers are rather harmless and cleaned
        # automatically anyway)
        with self.capture_triggers('social.ir_cron_post_scheduled') as captured_triggers:
            social_post.write({'scheduled_date': scheduled_date + timedelta(hours=1)})

        self.assertEqual(len(captured_triggers.records), 1)
        captured_trigger = captured_triggers.records[0]
        self.assertEqual(captured_trigger.call_at, scheduled_date + timedelta(hours=1))
        self.assertEqual(captured_trigger.cron_id, self.env.ref('social.ir_cron_post_scheduled'))

    @users('social_manager')
    def test_social_account_internals(self):
        """ Test social account creation, notably medium generation """
        vals_list = [{
            'name': 'TestAccount_%d' % x,
            'media_id': self.social_media.id,
        } for x in range(0, 5)]
        accounts = self.env['social.account'].create(vals_list)
        self.assertEqual(len(accounts.utm_medium_id), 5)
        self.assertEqual(
            set(accounts.mapped('utm_medium_id.name')),
            set(["[%s] TestAccount_%d" % (self.social_media.name, x) for x in range(0, 5)])
        )

        first_account = accounts[0]
        first_account.write({'name': 'Some Updated Name'})
        self.assertEqual(
            first_account.utm_medium_id.name,
            "[%s] Some Updated Name" % self.social_media.name
        )

    @users('social_user')
    def test_social_post_create_multi(self):
        """ Ensure that a 'multi' creation of 2 social.posts also
        creates 2 associated utm.sources. """
        social_posts = self.env['social.post'].create([{
            'account_ids': [(4, self.social_account.id)],
            'message': 'Message 1'
        }, {
            'account_ids': [(4, self.social_account.id)],
            'message': 'Message 2'
        }])

        self.assertEqual(2, len(social_posts))
        self.assertEqual(2, len(social_posts.utm_source_id))
        self.assertNotEqual(social_posts[0].utm_source_id, social_posts[1].utm_source_id)

    @classmethod
    def _get_social_media(cls):
        return cls.env['social.media'].create({
            'name': 'Social Media',
        })
