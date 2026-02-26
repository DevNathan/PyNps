import os
import warnings
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from matplotlib import font_manager, rc
import platform
import seaborn as sns
import re
import streamlit as st

company_name = st.text_input("회사명을 입력해 주세요", placeholder="검색할 회사명 입력")
