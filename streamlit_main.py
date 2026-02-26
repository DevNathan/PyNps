import os
import re
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st

class PensionData:
    def __init__(self, filepath):
        # pandas의 DtypeWarning 경고를 무시합니다.
        warnings.simplefilter(action='ignore', category=pd.errors.DtypeWarning)
        
        # 텍스트 정제를 위한 정규 표현식을 미리 컴파일하여 성능을 최적화합니다.
        self.pattern1 = re.compile(r'\([^)]+\)')
        self.pattern2 = re.compile(r'\[[^)]+\]')
        self.pattern3 = re.compile(r'[^A-Za-z0-9가-힣]')
        self.pattern4 = re.compile(r' +')
        
        # 지정된 파일 경로에서 CSV 데이터를 읽어옵니다.
        self.df = pd.read_csv(filepath, encoding='cp949')
        self.preprocess()

    def preprocess(self):
        # '사업장업종코드' 컬럼의 공백을 결측치로 변환 후, 유효한 데이터만 필터링합니다.
        mask = self.df['사업장업종코드'].replace({r'^\s+$': pd.NA}, regex=True).isna()
        df = self.df[~mask].copy()
        df['사업장업종코드'] = df['사업장업종코드'].astype('int32')

        # 분석에 용이하도록 직관적인 컬럼명으로 재정의합니다.
        df.columns = [
            '자료생성년월', '사업장명', '사업자등록번호', '가입상태', '우편번호',
            '사업장지번상세주소', '주소', '고객법정동주소코드', '고객행정동주소코드',
            '시도코드', '시군구코드', '읍면동코드',
            '사업장형태구분코드', '업종코드', '업종코드명',
            '적용일자', '재등록일자', '탈퇴일자',
            '가입자수', '금액', '신규', '상실'
        ]

        # 가입상태가 1(정상 유지)인 기업만 남겨 메모리 효율을 높입니다.
        df = df[df['가입상태'] == 1].reset_index(drop=True)

        # 분석에 사용하지 않는 불필요한 컬럼들을 제거합니다.
        df.drop(columns=[
            '자료생성년월', '우편번호', '사업장지번상세주소', '고객법정동주소코드', 
            '고객행정동주소코드', '사업장형태구분코드', '적용일자', '재등록일자', 
            '가입상태', '탈퇴일자'
        ], inplace=True)

        # 사업장명 데이터를 정제합니다.
        df['사업장명'] = df['사업장명'].apply(self.clean_company_name)

        # 주소 문자열에서 '시도' 지역구분 정보를 추출하여 새로운 컬럼으로 할당합니다.
        df['시도'] = df['주소'].str.split(' ').str[0]

        # 국민연금 요율 9%를 기준으로 인당 금액, 월 급여, 연간 급여 추정치를 계산합니다.
        df['인당금액'] = df['금액'] / df['가입자수']
        df['월급여추정'] = (df['인당금액'] / 9) * 100
        df['연간급여추정'] = df['월급여추정'] * 12
       
        self.df = df
   
    def clean_company_name(self, name):
        # (주), [주] 등의 특수문자 및 불필요한 기호를 제거하여 회사명을 정제합니다.
        if not isinstance(name, str):
            return name
        name = self.pattern1.sub('', name)
        name = self.pattern2.sub('', name)
        name = self.pattern3.sub(' ', name)
        name = self.pattern4.sub(' ', name)
        return name.strip()
   
    def find_company(self, company_name):
        # 입력받은 회사명이 포함된 데이터를 가입자수 기준으로 내림차순 정렬하여 반환합니다.
        return self.df.loc[
            self.df['사업장명'].str.contains(company_name, na=False), 
            ['사업장명', '월급여추정', '연간급여추정', '업종코드', '가입자수', '신규', '상실']
        ].sort_values('가입자수', ascending=False)
   
    def compare_company(self, company_name):
        # 검색된 회사의 업종코드와 동일한 동종업계의 급여 통계 데이터를 산출하여 비교합니다.
        company_search = self.find_company(company_name)
        if company_search.empty:
            return None

        code = company_search['업종코드'].iloc[0]
        summary_df = (
            self.df.loc[self.df['업종코드'] == code, ['월급여추정', '연간급여추정']]
            .agg(['mean', 'count', 'min', 'max'])
            .T
        )
        
        summary_df.index = ['업종_월급여추정', '업종_연간급여추정']
        summary_df.columns = ['평균', '개수', '최소', '최대']
        
        summary_df[company_name] = [
            company_search['월급여추정'].iloc[0], 
            company_search['연간급여추정'].iloc[0]
        ]
        
        return summary_df

    def company_info(self, company_name):
        # 검색된 기업의 상세 정보를 반환합니다. 결과가 없을 경우 None을 반환합니다.
        company_search = self.find_company(company_name)
        if company_search.empty:
            return None
        return self.df.loc[company_search.index[0]]
               
    def get_data(self):
        # 전처리가 완료된 전체 데이터프레임을 반환합니다.
        return self.df


# 국민연금공단 사업장 데이터 파일 경로를 지정합니다. (GitHub 원격 주소)
file_path = r'https://media.githubusercontent.com/media/DevNathan/PyNps/refs/heads/main/k-national-pension-2025-12.csv'

# Streamlit 캐싱을 활용하여 데이터 로딩 시간을 단축합니다.
@st.cache_resource
def read_pensiondata():
    return PensionData(file_path)

data = read_pensiondata()

# 사용자로부터 검색할 회사명을 입력받습니다.
company_name = st.text_input("회사명을 입력해 주세요", placeholder="검색할 회사명 입력")

if data and company_name:
    output = data.find_company(company_name=company_name)
    
    if len(output) > 0:
        st.subheader(output.iloc[0]["사업장명"])

        info = data.company_info(company_name=company_name)

        st.markdown(
            f"""
            - `{info['주소']}`
            - 업종코드명 `{info['업종코드명']}`
            - 총 근무자 `{int(info['가입자수']):,}` 명
            - 신규 입사자 `{info['신규']:,}` 명
            - 퇴사자 `{info['상실']:,}` 명
            """
        )

        col1, col2, col3 = st.columns(3)
        col1.text('월급여 추정')
        col1.markdown(f"`{int(output.iloc[0]['월급여추정']):,}` 원")

        col2.text('연봉 추정')
        col2.markdown(f"`{int(output.iloc[0]['연간급여추정']):,}` 원")

        col3.text('가입자수 추정')
        col3.markdown(f"`{int(output.iloc[0]['가입자수']):,}` 명")

        comp_output = data.compare_company(company_name)
        
        if comp_output is not None:
            st.dataframe(comp_output.round(0), use_container_width=True)

            st.markdown(f'### 업종 평균 VS {company_name} 비교')
            
            # 업종 평균과 검색된 기업의 월급여 추정액을 비교하여 백분율 차이를 계산합니다.
            percent_value = (info['월급여추정'] / comp_output.iloc[0, 0]) * 100 - 100
            
            # 월급여 및 연간급여 추정액 차이의 절댓값을 계산합니다.
            diff_month = abs(comp_output.iloc[0, 0] - info['월급여추정'])
            diff_year = abs(comp_output.iloc[1, 0] - info['연간급여추정'])
            
            # 백분율 값에 따라 출력할 비교 문구를 선택합니다.
            upordown = '높은' if percent_value > 0 else '낮은'
            
            # 계산된 비교 결과를 Markdown 형식으로 화면에 출력합니다.
            st.markdown(f"""
            - 업종 **평균 월급여**는 `{int(comp_output.iloc[0, 0]):,}` 원, **평균 연봉**은 `{int(comp_output.iloc[1, 0]):,}` 원 입니다.
            - `{company_name}`는 평균 보다 `{int(diff_month):,}` 원, :red[약 {abs(percent_value):.2f} %] `{upordown}` `{int(info['월급여추정']):,}` 원을 **월 평균 급여**로 받는 것으로 추정합니다.
            - `{company_name}`는 평균 보다 `{int(diff_year):,}` 원 `{upordown}` `{int(info['연간급여추정']):,}` 원을 **연봉**으로 받는 것으로 추정합니다.
            """)

            # 1행 2열의 서브플롯을 생성하여 시각화합니다.
            fig, axes = plt.subplots(1, 2)
            
            # 차트에 사용할 데이터 세트를 구성합니다.
            plot_data = [
                (0, 'Monthly Salary', comp_output.iloc[0, 0], info['월급여추정']),
                (1, 'Yearly Salary', comp_output.iloc[1, 0], info['연간급여추정'])
            ]

            # 반복문을 사용하여 중복 코드를 제거하고 두 개의 막대그래프를 생성합니다.
            for i, title, avg_val, comp_val in plot_data:
                ax = axes[i]
                bars = ax.bar(x=["Average", "Your Company"], height=[avg_val, comp_val], width=0.7)
                
                bars[0].set_color('black')
                bars[1].set_color('red')
                
                ax.bar_label(bars, fmt='%d')
                ax.ticklabel_format(style='plain', axis='y')
                ax.set_title(title)
                
                ax.tick_params(axis='both', which='major', labelsize=8, rotation=0)
                ax[i].tick_params(axis='both', which='minor', labelsize=6)

            plt.tight_layout()
            
            # Streamlit 화면에 플롯을 출력합니다.
            st.pyplot(fig)

            st.markdown('### 동종업계')
            df = data.get_data()
            
            # 동일 업종코드 데이터를 연간급여추정 순으로 상위 10개 추출하여 출력합니다.
            industry_top10 = (
                df.loc[df['업종코드'] == info['업종코드'], ['사업장명', '월급여추정', '연간급여추정', '가입자수']]
                .sort_values('연간급여추정', ascending=False)
                .head(10)
                .round(0)
            )
            st.dataframe(industry_top10, use_container_width=True)
            
    else:
        st.subheader("검색결과가 없습니다.")
