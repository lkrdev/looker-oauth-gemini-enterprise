# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Shared constants across the CA API Agent."""

# Display pagination configurations
DATA_MESSAGE_DISPLAY_MAX_ROWS = 5
DATA_TABLE_DISPLAY_MAX_ROWS = 50

# Deterministic ADK state keys
DATA_RESULT_STATE_KEY = "temp:data_result"
SUMMARY_STATE_KEY = "temp:summary_data"
VEGA_LITE_SPEC_STATE_KEY = "temp:vega_lite_spec"
CURRENT_SYSTEM_MESSAGES_STATE_KEY = "temp:current_system_messages"

# Debug / Raw Analytics output flags
RAW_RESULTS = True