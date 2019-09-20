# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import dateutil.parser
import requests

from odoo import models, fields, api
from werkzeug.urls import url_join


class SocialStreamTwitter(models.Model):
    _inherit = 'social.stream'

    twitter_searched_keyword = fields.Char('Search Keyword')
    twitter_followed_account_search = fields.Char('Search User')
    # TODO awa: clean unused 'social.twitter.account' in a cron job
    twitter_followed_account_id = fields.Many2one('social.twitter.account')

    def _apply_default_name(self):
        for stream in self:
            if stream.media_id.media_type == 'twitter':
                if stream.stream_type_id.stream_type in ['twitter_follow', 'twitter_likes'] and stream.twitter_followed_account_id:
                    stream.write({'name': '%s: %s' % (stream.stream_type_id.name, stream.twitter_followed_account_id.name)})
                elif stream.stream_type_id.stream_type == 'twitter_user_mentions' and stream.account_id:
                    stream.write({'name': '%s: %s' % (stream.stream_type_id.name, stream.account_id.name)})
                elif stream.stream_type_id.stream_type == 'twitter_keyword' and stream.twitter_searched_keyword:
                    stream.write({'name': '%s: %s' % (stream.stream_type_id.name, stream.twitter_searched_keyword)})
            else:
                super(SocialStreamTwitter, stream)._apply_default_name()

    def _fetch_stream_data(self):
        twitter_streams = self.filtered(lambda account: account.media_id.media_type == 'twitter')
        super(SocialStreamTwitter, (self - twitter_streams))._fetch_stream_data()

        for stream in twitter_streams:
            if stream.stream_type_id.stream_type == 'twitter_user_mentions':
                stream._fetch_tweets('statuses/mentions_timeline')
            elif stream.stream_type_id.stream_type == 'twitter_follow':
                stream._fetch_tweets('statuses/user_timeline', {'user_id': stream.twitter_followed_account_id.twitter_id})
            elif stream.stream_type_id.stream_type == 'twitter_likes':
                stream._fetch_tweets('favorites/list', {'user_id': stream.twitter_followed_account_id.twitter_id})
            elif stream.stream_type_id.stream_type == 'twitter_keyword':
                stream._fetch_tweets('search/tweets', {'q': stream.twitter_searched_keyword + ' -filter:retweets', 'result_type': 'recent'})

    def _fetch_tweets(self, endpoint_name, extra_params={}):
        self.ensure_one()

        query_params = {
            'tweet_mode': 'extended',
            'count': 100
        }
        query_params.update(extra_params)
        tweets_endpoint_url = url_join(self.env['social.media']._TWITTER_ENDPOINT, "/1.1/%s.json" % endpoint_name)
        # TODO awa: check the "TE" header (Transfer-Encoding) to get a (smaller) gzip response
        headers = self.account_id._get_twitter_oauth_header(
            tweets_endpoint_url,
            params=query_params,
            method='GET'
        )
        result = requests.get(
            tweets_endpoint_url,
            query_params,
            headers=headers
        )

        result_tweets = result.json() if endpoint_name != 'search/tweets' else result.json().get('statuses')
        if isinstance(result_tweets, dict) and result_tweets.get('errors'):
            self.account_id.sudo().write({'is_media_disconnected': True})
            return

        tweets_ids = [tweet.get('id_str') for tweet in result_tweets]
        existing_tweets = self.env['social.stream.post'].sudo().search([
            ('stream_id', '=', self.id),
            ('twitter_tweet_id', 'in', tweets_ids)
        ])
        existing_tweets_by_tweet_id = {
            tweet.twitter_tweet_id: tweet for tweet in existing_tweets
        }

        # TODO awa: handle deleted tweets ?
        tweets_to_create = []

        favorites_by_id = self._lookup_tweets([tweet.get('id_str') for tweet in result_tweets])

        for tweet in result_tweets:
            values = {
                'stream_id': self.id,
                'message': tweet.get('full_text'),
                'author_name': tweet.get('user').get('name'),
                'published_date': fields.Datetime.from_string(dateutil.parser.parse(tweet.get('created_at')).strftime('%Y-%m-%d %H:%M:%S')),
                'twitter_likes_count': tweet.get('favorite_count'),
                'twitter_user_likes': favorites_by_id.get(tweet.get('id_str'), {'favorited': False})['favorited'],
                'twitter_retweet_count': tweet.get('retweet_count'),
                'twitter_tweet_id': tweet.get('id_str'),
                'twitter_author_id': tweet.get('user').get('id_str'),
                'twitter_screen_name': tweet.get('user').get('screen_name'),
                'twitter_profile_image_url': tweet.get('user').get('profile_image_url_https')
            }

            existing_tweet = existing_tweets_by_tweet_id.get(tweet.get('id_str'))
            if existing_tweet:
                existing_tweet.write(values)
            else:
                # attachments are only extracted for new posts
                values.update(self._extract_twitter_attachments(tweet))
                tweets_to_create.append(values)

        self.env['social.stream.post'].sudo().create(tweets_to_create)

    @api.model
    def _extract_twitter_attachments(self, tweet):
        result = {}

        images = []
        images_urls = []
        for attachment in tweet.get('extended_entities', {}).get('media', []):
            if attachment.get('type') == 'photo':
                image_url = attachment.get('media_url_https')
                images_urls.append(image_url)
                images.append({
                    'image_url': image_url
                })

        if images:
            result.update({
                'stream_post_image_ids': [(0, 0, attachment) for attachment in images],
            })

        return result

    def _lookup_tweets(self, tweet_ids):
        """ Search API doesn't correctly supply the 'favorited' status of the tweet.
        Solution suggested by twitter: lookup the IDs again...
        Check: https://twittercommunity.com/t/favorited-reports-as-false-even-if-status-is-already-favorited-by-the-user/11145/7

        This method will lookup all provided tweets and return a dict containing {'tweet_id': favorited} """

        page = 1
        lookup_endpoint_ul = url_join(self.env['social.media']._TWITTER_ENDPOINT, "/1.1/statuses/lookup.json")
        favorites_by_id = {}
        while len(tweet_ids) >= ((page - 1) * 100):
            start = (page - 1) * 100
            end = start + 100
            params = {
                'id': ','.join(tweet_ids[start:end])
            }
            headers = self.account_id._get_twitter_oauth_header(
                lookup_endpoint_ul,
                params=params
            )
            result = requests.post(
                lookup_endpoint_ul,
                data=params,
                headers=headers
            )

            favorites_by_id.update({
                tweet.get('id_str'): {
                    'favorited': tweet.get('favorited', False)
                }
                for tweet in result.json()
            })

            page += 1

        return favorites_by_id
