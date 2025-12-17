"""
Copyright (c) 2025, Center for Coastal and Ocean Mapping, University of New Hampshire
All rights reserved.

This file is part of BISTplotter and is licensed under the BSD 3-Clause License.
See LICENSE file in the project root for full license details.

Commonly used file handling functions for NOAA / MAC echosounder assessment tools
"""

import os
import datetime

from PyQt6 import QtWidgets, QtGui
from PyQt6.QtGui import QDoubleValidator, QColor
from PyQt6.QtCore import Qt, QSize


def get_current_file_list(self):  # get current list of files in qlistwidget
	list_items = []
	for f in range(self.file_list.count()):
		list_items.append(self.file_list.item(f))

	self.filenames = [f.data(1) for f in list_items]  # return list of full file paths stored in item data, role 1


def add_files(self, ftype_filter, input_dir='HOME', include_subdir=False, multiselect=True):
	print(f"DEBUG: add_files called with ftype_filter={ftype_filter}, input_dir={input_dir}, include_subdir={include_subdir}, multiselect={multiselect}")
	# add files selected individually (if input_dir is not passed) or from directories (if input_dir is specified or [])
	
	# Try to load session config for last used directories (only when input_dir is 'HOME')
	default_dir = os.getenv('HOME')
	print(f"DEBUG: default_dir={default_dir}")
	if input_dir == 'HOME':
		try:
			# Try swath coverage config first, fall back to swath accuracy config
			try:
				from multibeam_tools.libs.swath_coverage_lib import load_session_config
				config = load_session_config()
			except ImportError:
				from multibeam_tools.libs.swath_accuracy_lib import load_session_config
				config = load_session_config()
			
			# Use appropriate directory based on file type
			if 'xyz' in ftype_filter or 'Reference surface' in ftype_filter:
				default_dir = config.get("last_xyz_dir", default_dir)
			elif 'xyd' in ftype_filter or 'Density surface' in ftype_filter:
				default_dir = config.get("last_xyd_dir", default_dir)
			elif 'tid' in ftype_filter or 'Tide' in ftype_filter:
				default_dir = config.get("last_tide_dir", default_dir)
			elif 'all' in ftype_filter or 'kmall' in ftype_filter or 'ASCII' in ftype_filter or 'Crossline' in ftype_filter:
				default_dir = config.get("last_crossline_dir", default_dir)
			elif 'pkl' in ftype_filter or 'archive' in ftype_filter.lower() or 'Saved swath coverage data' in ftype_filter:
				default_dir = config.get("last_archive_dir", default_dir)
			elif 'txt' in ftype_filter or 'Theoretical coverage curve' in ftype_filter:
				default_dir = config.get("last_spec_dir", default_dir)
			print(f"DEBUG: After config lookup, default_dir={default_dir}")
		except Exception as e:
			print(f"DEBUG: Exception loading session config: {e}")
			pass  # Fall back to HOME if session config is not available
	
	if input_dir == []:  # select directory if input_dir is passed as []
		input_dir = QtWidgets.QFileDialog.getExistingDirectory(self, 'Add directory', default_dir)
		# input_dir = QtWidgets.QFileDialog.getExistingDirectory(self, 'Add directory', os.getenv('HOME'))

	if input_dir == 'HOME':  # select files manually if input_dir not specified as optional argument
		print(f"DEBUG: Opening file dialog with default_dir={default_dir}, ftype_filter={ftype_filter}")
		# ftype_filter must be formatted for getOpenFileNames, e.g., 'Kongsberg (*.all *.kmall)'
		if multiselect:
			print("DEBUG: Using getOpenFileNames (multiselect)")
			fnames = QtWidgets.QFileDialog.getOpenFileNames(self, 'Open files...', default_dir, ftype_filter)
			print(f"DEBUG: getOpenFileNames returned: {fnames}")
			fnames = fnames[0]  # keep only the filenames in first list item returned from getOpenFileNames

		else:  # allow only one (getOpenFileName returns tuple (fname, filter)
			print("DEBUG: Using getOpenFileName (single select)")
			fname, filt = QtWidgets.QFileDialog.getOpenFileName(self, 'Open file...', default_dir, ftype_filter)
			print(f"DEBUG: getOpenFileName returned: fname={fname}, filt={filt}")
			fnames = [fname]  # match list style used for multiselect

		print(f"DEBUG: Final fnames list: {fnames}")
		# print('in add_files, multiselect =', multiselect, 'and fnames = ', fnames)
		
		# Save the directory where files were selected from for next session
		if fnames and len(fnames) > 0:
			try:
				# Extract directory from first file
				file_dir = os.path.dirname(fnames[0])
				if file_dir:
					# Try to save to swath coverage config first, fall back to swath accuracy config
					try:
						from multibeam_tools.libs.swath_coverage_lib import update_last_directory
						if 'all' in ftype_filter or 'kmall' in ftype_filter or 'ASCII' in ftype_filter or 'Crossline' in ftype_filter:
							update_last_directory("last_crossline_dir", file_dir)
						elif 'pkl' in ftype_filter or 'archive' in ftype_filter.lower() or 'Saved swath coverage data' in ftype_filter:
							update_last_directory("last_archive_dir", file_dir)
						elif 'txt' in ftype_filter or 'Theoretical coverage curve' in ftype_filter:
							update_last_directory("last_spec_dir", file_dir)
						elif 'xyz' in ftype_filter or 'Reference surface' in ftype_filter:
							update_last_directory("last_xyz_dir", file_dir)
						elif 'xyd' in ftype_filter or 'Density surface' in ftype_filter:
							update_last_directory("last_xyd_dir", file_dir)
						elif 'tid' in ftype_filter or 'Tide' in ftype_filter:
							update_last_directory("last_tide_dir", file_dir)
					except ImportError:
						from multibeam_tools.libs.swath_accuracy_lib import update_last_directory
						if 'all' in ftype_filter or 'kmall' in ftype_filter or 'ASCII' in ftype_filter or 'Crossline' in ftype_filter:
							update_last_directory("last_crossline_dir", file_dir)
						elif 'pkl' in ftype_filter or 'archive' in ftype_filter.lower() or 'Saved swath coverage data' in ftype_filter:
							update_last_directory("last_archive_dir", file_dir)
						elif 'txt' in ftype_filter or 'Theoretical coverage curve' in ftype_filter:
							update_last_directory("last_spec_dir", file_dir)
						elif 'xyz' in ftype_filter or 'Reference surface' in ftype_filter:
							update_last_directory("last_xyz_dir", file_dir)
						elif 'xyd' in ftype_filter or 'Density surface' in ftype_filter:
							update_last_directory("last_xyd_dir", file_dir)
						elif 'tid' in ftype_filter or 'Tide' in ftype_filter:
							update_last_directory("last_tide_dir", file_dir)
			except Exception as e:
				print(f"Warning: Could not save directory to session config: {e}")

	else:  # get all files satisfying ftype_filter in input_dir
		# ftype filter must be formatted as list of file extensions to accept, e.g., ['.all', '.kmall']
		fnames = []

		if include_subdir:  # walk through this dir and all subdir
			print('looking in subdirs in add_files with input_dir =', input_dir, ' and type_filter=', ftype_filter)
			for dirpath, dirnames, filenames in os.walk(input_dir):
				# print('currently looking at ', dirpath, dirnames, filenames)
				# for filename in [f for f in filenames if f.endswith(ftype_filter)]:
				for filename in [f for f in filenames if os.path.splitext(f)[1] in ftype_filter]:
					# print('currently joining and appending ', dirpath, filename)
					fnames.append(os.path.join(dirpath, filename).replace('\\', '/'))

		else:  # add files from this dir only
			print('looking in this directory only with input_dir =', input_dir, ' and ftype_filter=', ftype_filter)
			for f in os.listdir(input_dir):
				if os.path.isfile(os.path.join(input_dir, f)):  # verify it's a file
					if os.path.splitext(f)[1] in ftype_filter:  # verify ftype_filter extension
						fnames.append(os.path.join(input_dir, f).replace('\\', '/'))  # add path like getOpenFileNames

	return fnames


def update_file_list(self, fnames, verbose=True):
	# get updated file list and add selected files only if not already listed
	if not fnames:
		update_log(self, 'No files selected')
		return

	get_current_file_list(self)
	fnames_new = [fn for fn in fnames if fn not in self.filenames]
	fnames_skip = [fs for fs in fnames if fs in self.filenames]

	if len(fnames_skip) > 0:  # skip any files already added, update log
		update_log(self, 'Skipping ' + str(len(fnames_skip)) + ' file(s) already added')
	# if len(fnames_new) > 0:
	i = 0
	for f in range(len(fnames_new)):  # add item with full file path as data field, show/hide path text
		try:
			[path, fname] = fnames_new[f].rsplit('/', 1)
			if fname.rsplit('.', 1)[0]:  # add file only if name exists prior to ext (may pass splitext check if adding dir)
				new_item = QtWidgets.QListWidgetItem()
				new_item.setData(1, fnames_new[f])  # set full file path as data, role 1
				# Check if show_path_chk exists, default to False if not
				show_path = False
				if hasattr(self, 'show_path_chk'):
					show_path = self.show_path_chk.isChecked()
				new_item.setText((path + '/') * int(show_path) + fname)  # set text, show or hide path
				self.file_list.addItem(new_item)
				if verbose:
					update_log(self, 'Added ' + fname)  # fnames_new[f].rsplit('/',1)[-1])

				i+=1  # update file added counter

			else:  # skip file if nothing found prior to extension
				update_log(self, 'Skipping empty filename ' + fname)

		except ValueError:
			update_log(self, 'Skipping filename with error: ' + (fnames_new[f] if len(fnames_new[f]) > 0 else '[empty]'))

	update_log(self, 'Added ' + str(i) + ' new file(s)')
	
	# Update self.filenames after adding items to the widget
	get_current_file_list(self)


def get_new_file_list(self, fext=[''], flist_old=[]):
	# determine list of new files with file extension fext that do not exist in flist_old
	# flist_old may contain paths as well as file names; compare only file names
	get_current_file_list(self)
	if fext == ['']:
		fnames_ext = [fn for fn in self.filenames]
		print('fext == [''], got fnames_ext = ', fnames_ext)
	else:
		fnames_ext = [fn for fn in self.filenames if any(ext in fn for ext in fext)]
		print('fext =', fext, ' got fnames_ext =', fnames_ext)

	fnames_old = [fn.split('/')[-1] for fn in flist_old]  # file names only (no paths) from flist_old
	fnames_new = [fn for fn in fnames_ext if fn.split('/')[-1] not in fnames_old]  # check if fname in fnames_old

	print('returning from get_new_file_list')
	print("DEBUG: self.filenames =", self.filenames)
	print("DEBUG: flist_old =", flist_old)
	return fnames_new  # return the fnames_new (with paths)


def get_output_dir(self):
	# get output directory for writing files
	try:
		# Load last used output directory - try swath coverage config first, fall back to swath accuracy config
		try:
			from multibeam_tools.libs.swath_coverage_lib import load_session_config, update_last_directory
			config = load_session_config()
			last_dir = config.get("last_output_dir", os.getenv('HOME'))
		except ImportError:
			# Fall back to swath accuracy config if swath coverage config is not available
			from multibeam_tools.libs.swath_accuracy_lib import load_session_config, update_last_directory
			config = load_session_config()
			last_dir = config.get("last_output_dir", os.getenv('HOME'))
		
		new_output_dir = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select output directory', last_dir)

		if new_output_dir != '':  # update output directory if not cancelled
			self.output_dir = new_output_dir
			update_log(self, 'Selected output directory: ' + self.output_dir)
			self.current_outdir_lbl.setText('Current output directory: ' + self.output_dir)
			
			# Save the selected directory for next session
			update_last_directory("last_output_dir", new_output_dir)

	except:
		update_log(self, 'No output directory selected.')
		pass


def remove_files(self, clear_all=False):
	# remove selected files
	print('in remove_files with clear_all=', clear_all)
	# self.get_current_file_list()
	get_current_file_list(self)
	selected_files = self.file_list.selectedItems()
	print('selected_files =', selected_files)
	removed_files = []

	# elif not selected_files:  # files exist but nothing is selected
	if clear_all:  # clear all
		removed_files = self.filenames
		self.file_list.clear()
		self.filenames = []

	elif self.filenames and not selected_files:  # files exist but nothing is selected
		update_log(self, 'No files selected for removal.')

	else:  # remove only the files that have been selected
		for f in selected_files:
			fname = f.text().split('/')[-1]
			self.file_list.takeItem(self.file_list.row(f))
			update_log(self, 'Removed ' + fname)
			removed_files.append(f)
			# removed_files.append(f.text())

	return removed_files


# def clear_files(self):
# 	clear all files from the file list and plot
# 	self.remove_files(clear_all=True)
	# remove_files(self, clear_all=True)
	# update_log(self, 'Cleared all files')
	# self.current_file_lbl.setText('Current File [0/0]:')
	# self.calc_pb.setValue(0)


def update_log(self, entry, font_color='black'):  # update the activity log
    # Use enhanced logging if available (MainWindow has enhanced update_log method)
    if hasattr(self, 'update_log') and hasattr(self.update_log, '__self__'):
        # This is the enhanced MainWindow.update_log method
        self.update_log(entry, font_color)
    else:
        # Fallback to basic logging
        try:
            self.log.setTextColor(QColor(font_color))
            self.log.append(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' ' + entry)
            QtWidgets.QApplication.processEvents()
        except Exception as e:
            # Ultimate fallback to print if log widget fails
            print(f"Logging error: {e}")
            print(f"Original entry: {entry}")


def update_prog(self, total_prog):
	self.calc_pb.setValue(total_prog)
	QtWidgets.QApplication.processEvents()


def show_file_paths(self): #, show_path=False):
	# show or hide path for all items in file_list according to show_paths_chk selection
	# for i in range(self.file_list.count()):
	print('in show_file_paths with self.file_list.count()=', self.file_list.count())
	
	# Check if show_path_chk exists, default to False if not
	show_path = False
	if hasattr(self, 'show_path_chk'):
		show_path = self.show_path_chk.isChecked()
	
	for i in range(self.file_list.count()):
		[path, fname] = self.file_list.item(i).data(1).rsplit('/', 1)  # split full file path from item data, role 1
		self.file_list.item(i).setText((path + '/') * int(show_path) + fname)
		# self.file_list.item(i).setText((path + '/') * int(show_path) + fname)


def update_system_info(self, det, force_update=False, fname_str_replace=''):
	# update model, serial number, ship, cruise info based on detection info and/or custom fields
	if self.custom_info_gb.isChecked():  # use custom info if checked
		self.ship_name = self.ship_tb.text()
		self.cruise_name = self.cruise_tb.text()
		self.model_name = self.model_cbox.currentText()

	else:  # get info from detections if available
		try:  # try to grab ship name from filenames (conventional file naming with ship info after third '_')
			# temp_ship_name = det['fname'][0]  # first fname, remove trimmed suffix/file ext, keep name after 3rd
			temp_ship_name = ' '.join(det['fname'][0].replace(fname_str_replace, '').split('.')[0].split('_')[3:])
			self.ship_name = temp_ship_name.split('EM')[0].strip()  # remove model suffix if present

		except:
			self.ship_name = 'Ship Name N/A'  # if ship name not available in filename

		if not self.ship_name_updated or force_update:
			self.ship_tb.setText(self.ship_name)  # update custom info text box
			update_log(self, 'Updated ship name to ' + self.ship_tb.text() + ' (first file name ending)')
			self.ship_name_updated = True

		try:  # try to get cruise name from Survey ID field in
			self.cruise_name = self.data_new[0]['IP_start'][0]['SID'].upper()  # update cruise ID with Survey ID

		except:
			self.cruise_name = 'Cruise N/A'

		if not self.cruise_name_updated or force_update:
			self.cruise_tb.setText(self.cruise_name)  # update custom info text box
			update_log(self, 'Updated cruise name to ' + self.cruise_tb.text() + ' (first survey ID found, if any)')
			self.cruise_name_updated = True

		try:
			self.model_name = 'EM ' + str(det['model'][0])

			if not self.model_updated or force_update:
				self.model_cbox.setCurrentIndex(self.model_cbox.findText(self.model_name))
				update_log(self, 'Updated model to ' + self.model_cbox.currentText() + ' (first model found)')
				self.model_updated = True

		except:
			self.model_name = 'Model N/A'

		try:
			self.sn = str(det['sn'][0])

			if not self.sn_updated or force_update:
				update_log(self, 'Updated serial number to ' + self.sn + ' (first s/n found)')
				self.sn_updated = True

		except:
			self.sn = 'S/N N/A'



########### TESTING LOOP METHOD FOR UPDATING SYSTEM INFO


# def update_system_info(self, det, force_update=False, fname_str_replace=''):
# 	# update model, serial number, ship, cruise info based on detection info and/or custom fields
# 	sys_info = {'ship_name': {'var': self.ship_name,  #'tb': self.ship_tb,
# 							  'default': 'Ship Name N/A',
# 							  'source': '' if not 'fname' in det.keys() else\
# 								  ' '.join(det['fname'][0].replace(fname_str_replace, '').split('.')[0].split('_')[3:]),
# 							  'set_widget': self.ship_tb.setText(self.ship_name),
# 							  'updated': self.ship_name_updated},
#
# 				# 'cruise_name': {'var': self.cruise_name, 'tb': self.cruise_tb, 'default': 'Cruise N/A',
# 				# 				'source': self.data_new[0]['IP_start'][0]['SID'].upper(),
# 				# 				'set_widget': self.cruise_tb.setText(self.cruise_name),
# 				# 				'updated': self.cruise_name_updated},
# 				#
# 				# 'model_name': {'var': self.model_name, 'tb': self.model_tb, 'default': 'Model N/A',
# 				# 			   'source': 'EM ' + str(det['model'][0]),
# 				# 			   'set_widget': self.model_cbox.setCurrentIndex(self.model_cbox.findText(self.model_name)),
# 				# 			   'updated': self.model_updated},
# 				#
# 				# 'sn': {'var': self.sn, 'tb': None, 'default': 'S/N N/A',
# 				# 	   'source': str(det['sn'][0]),
# 				# 	   'set_widget': update_log(self, 'Placeholder for updating SN textbox'),
# 				# 	   'updated': self.sn_updated},
# 				}
#
# 	for k, v in sys_info.items():  # loop through all sys_info items and try to update accordingly
# 		print('working on k, v = ', k, v)
# 		try:
#
# 			eval(k + '=v')
# 			setattr(k, 'var', k['source'])
#
# 			if not k['updated'] or force_update:
# 				k['set_widget']
# 				update_log(self, 'Updated ' + k['default'].split()[0].lower() + ' to ' + k['var'])
# 				k['updated'] = True
#
# 		except:
# 			setattr(k, 'var', k['default'])
#
# 			# k['var'] = k['default']
#
############################################################################3
