# -*- coding: utf-8 -*-
import urllib.request, urllib.error, urllib.parse
import xml.etree.ElementTree as ET
from binascii import hexlify, unhexlify
from Crypto.Cipher import AES
from PIL import Image
from IconManager import IconManager
from datetime import datetime, timezone
import sys, logging, struct, hashlib, math, unicodedata, json
import common


class TitleInfo:
				
	def __init__(self, id, uid = None):
		self.id = id.upper()
		self.uid = uid
		self.name = None
		self.product_code = None
		self.regions = 0
		self.country_code = None
		self.features = []
		
		self.feature_list = {}
		
		self.fetch_data()

		        
	def take_my_flist(self):
		return self.feature_list
		
	@staticmethod
	def get_id_pairs(id_list, get_content_id = True):
		ret = [None] * len(id_list)
		from_key = 'title_id' if get_content_id else 'ns_uid'
		to_key = 'title_id' if not get_content_id else 'ns_uid'
		# URI length is limited, so need to break up large requests
		limit = 40
		if len(id_list) > limit:
			ret = []
			ret += TitleInfo.get_id_pairs(id_list[:limit], get_content_id)
			ret += TitleInfo.get_id_pairs(id_list[limit:], get_content_id)
		else:
			try:
				shop_request = urllib.request.Request(common.ninja_url + "titles/id_pair?{}[]=".format(from_key) + ','.join(id_list))
				shop_request.get_method = lambda: 'GET'
				response = urllib.request.urlopen(shop_request, context=common.ctr_context)
				xml = ET.fromstring(response.read().decode('UTF-8', 'replace'))
				for el in xml.findall('*/title_id_pair'):
					index = id_list.index(el.find(from_key).text)
					ret[index] = el.find(to_key).text
			except urllib.error.URLError as e:
				self.logger.error(e)
		return ret;
		
	def try_regions(self, region_list, try_all):
		title_response = None
		for code in region_list:
			try:
				if self.country_code and (code in common.region_euro_array) and (self.regions & common.region_map['EU']):
					continue
				title_request = urllib.request.Request(common.samurai_url + code + '/title/' + self.uid + '/?shop_id=1')
				title_response = urllib.request.urlopen(title_request, context=common.ctr_context)
				if not self.country_code:
					self.country_code = code
			except urllib.error.URLError as e:
				pass
			else:
				if code in common.region_euro_array:
					self.regions |= common.region_map['EU']
				elif code in common.region_map:
					self.regions |= common.region_map[code]
				if not try_all:
					break
		return title_response


	def fetch_data(self):
		if self.regions:
			if self.regions == common.region_map['US']:
				self.country_code = 'US'
				self.name = None # Use the title provided by samurai instead of icon server
			elif self.regions == common.region_map['JP']:
				self.country_code = 'JP'
			elif self.regions & common.region_map['EU']:
				if not self.regions & common.region_map['US']:
					title_response = self.try_regions(common.region_euro_array, False)
				else:
					# self.country_code = 'GB'
					title_response = self.try_regions(["GB","JP"], False)
				self.name = None
			elif self.regions & common.region_map['JP']:
				self.country_code = 'JP'
			elif self.regions & common.region_map['KO']:
				self.country_code = 'KR'
			elif self.regions & common.region_map['CN']:
				self.country_code = 'HK'
			elif self.regions & common.region_map['TW']:
				self.country_code = 'TW'
			else:
				self.logger.error("Region value {} for {}?".format(self.regions, self.id))
				return

			if self.country_code and not title_response:
				try:
					title_request = urllib.request.Request(common.samurai_url + self.country_code + '/title/' + self.uid + '/?shop_id=1')
					title_response = urllib.request.urlopen(title_request, context=common.ctr_context)
				except urllib.error.HTTPError:
					print(common.samurai_url + self.country_code + '/title/' + self.uid + '/?shop_id=1')
		else:
			# If all else fails, try all regions to see which the title is from
			self.regions = 0
			title_response = self.try_regions(common.region_array, True)

		if not self.regions or not title_response:
			raise ValueError("No region or country code for {}".format(self.id))
				
		# Use JP region for later timezone for pre-releases (this was added for Pokemon S/M lol)
		ec_country_code = 'JP' if (self.regions & common.region_map['JP']) else self.country_code
				
		ec_response = urllib.request.urlopen(common.ninja_url + ec_country_code + '/title/' + self.uid + '/ec_info', context=common.ctr_context)
		xml = ET.fromstring(title_response.read().decode('UTF-8', 'replace'))
		self.product_code = xml.find("*/product_code").text
		if not self.name:
			self.name = xml.find("*/name").text.replace('\n', ' ').strip()

		# Get features
		features = xml.findall(".//feature")
		if features:
			for feature in list(features):
				self.features.append(int(feature.find("id").text))
				if self.country_code == "EU" or self.country_code == "US" or self.country_code == "GB":
					self.feature_list[int(feature.find("id").text)] = feature.find("name").text
					print("Feature #{}: {}".format(feature.find("id").text, feature.find("name").text))
