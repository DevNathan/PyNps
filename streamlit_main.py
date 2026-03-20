import os
import re
import warnings
import pandas as pd
import streamlit as st
import plotly.express as px

class PensionData:
    def __init__(self, filepath):
        warnings.simplefilter(action='ignore', category=pd.errors.DtypeWarning)
        
        self.pattern1 = re.compile(r'\([^)]+\)')
        self.pattern2 = re.compile(r'\[[^)]+\]')
        self.pattern3 = re.compile(r'[^A-Za-z0-9가-힣]')
        self.pattern4 = re.compile(r' +')
        
        self.df = pd.read_csv(filepath, encoding='cp949')
        self.preprocess()

    # 데이터 전처리
    def preprocess(self):
        """
        데이터프레임의 결측치를 처리하고 불필요한 컬럼을 제거하며,
        국민연금 요율을 바탕으로 급여 추정치를 계산
        """
        mask = self.df['사업장업종코드'].replace({r'^\s+$': pd.NA}, regex=True).isna()
        df = self.df[~mask].copy()
        df['사업장업종코드'] = df['사업장업종코드'].astype('int32')

        df.columns = [
            '자료생성년월', '사업장명', '사업자등록번호', '가입상태', '우편번호',
            '사업장지번상세주소', '주소', '고객법정동주소코드', '고객행정동주소코드',
            '시도코드', '시군구코드', '읍면동코드',
            '사업장형태구분코드', '업종코드', '업종코드명',
            '적용일자', '재등록일자', '탈퇴일자',
            '가입자수', '금액', '신규', '상실'
        ]

        df = df[df['가입상태'] == 1].reset_index(drop=True)

        df.drop(columns=[
            '자료생성년월', '우편번호', '사업장지번상세주소', '고객법정동주소코드', 
            '고객행정동주소코드', '사업장형태구분코드', '적용일자', '재등록일자', 
            '가입상태', '탈퇴일자'
        ], inplace=True)

        df['사업장명'] = df['사업장명'].apply(self.clean_company_name)
        df['시도'] = df['주소'].str.split(' ').str[0]

        df['인당금액'] = df['금액'] / df['가입자수']
        df['월급여추정'] = (df['인당금액'] / 9) * 100
        df['연간급여추정'] = df['월급여추정'] * 12
        
        self.df = df
    
    def clean_company_name(self, name):
        """
        회사명에 포함된 특수문자 및 괄호 내용을 제거하여 문자열 정제
        """
        if not isinstance(name, str):
            return name
        name = self.pattern1.sub('', name)
        name = self.pattern2.sub('', name)
        name = self.pattern3.sub(' ', name)
        name = self.pattern4.sub(' ', name)
        return name.strip()
    
    def find_company(self, company_name):
        """
        입력된 문자열이 포함된 사업장 데이터를 가입자 수 기준 내림차순으로 검색하는 기능
        """
        return self.df.loc[
            self.df['사업장명'].str.contains(company_name, na=False), 
            ['사업장명', '월급여추정', '연간급여추정', '업종코드', '가입자수', '신규', '상실']
        ].sort_values('가입자수', ascending=False)
    
    def compare_company(self, company_name):
        """
        특정 기업의 급여와 동일 업종의 평균 급여 데이터를 산출하여 비교 데이터프레임으로 반환
        """
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
        """
        검색된 첫 번째 기업의 전체 상세 정보
        """
        company_search = self.find_company(company_name)
        if company_search.empty:
            return None
        return self.df.loc[company_search.index[0]]
                
    def get_data(self):
        return self.df

# 스트림릿에 캐싱
file_path = r'https://media.githubusercontent.com/media/DevNathan/PyNps/refs/heads/main/k-national-pension-2025-12.csv'
@st.cache_resource
def read_pensiondata():
    return PensionData(file_path)

# ----------------------------------------------------------------------------- UI

st.set_page_config(page_title="기업 연봉 분석 대시보드", layout="wide")

st.title("기업 연봉 분석 대시보드")
st.markdown("**국민연금공단 데이터를 기반으로 기업의 추정 연봉과 동종업계 수준을 비교합니다.**")

data = read_pensiondata()

company_name = st.text_input("분석할 기업명을 입력하십시오", placeholder="예: 삼성전자")

if data and company_name:
    output = data.find_company(company_name=company_name)
    
    if not output.empty:
        info = data.company_info(company_name=company_name)
        comp_output = data.compare_company(company_name)
        
        target_name = output.iloc[0]["사업장명"]
        avg_monthly = comp_output.iloc[0, 0]
        avg_yearly = comp_output.iloc[1, 0]
        target_monthly = info['월급여추정']
        target_yearly = info['연간급여추정']

        st.divider()
        st.header(target_name)
        st.caption(f"📍 {info['주소']} | 🏷️ 업종: {info['업종코드명']}")
        
        # 핵심 지표를 Metric 컴포넌트로 직관적으로 표시합니다.
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("추정 월급여", f"{int(target_monthly):,} 원", f"{int(target_monthly - avg_monthly):,} 원 (업종대비)")
        col2.metric("추정 연봉", f"{int(target_yearly):,} 원", f"{int(target_yearly - avg_yearly):,} 원 (업종대비)")
        col3.metric("총 근무자", f"{int(info['가입자수']):,} 명")
        col4.metric("인력 변동", f"+{info['신규']} / -{info['상실']}")

        st.divider()
        
        # Plotly를 사용한 현대적인 막대 그래프 시각화
        st.subheader("📊 동종업계 평균 급여 비교")
        
        chart_data = pd.DataFrame({
            "구분": ["업종 평균", target_name, "업종 평균", target_name],
            "금액": [avg_monthly, target_monthly, avg_yearly, target_yearly],
            "카테고리": ["월급여", "월급여", "연봉", "연봉"]
        })

        fig = px.bar(
            chart_data, 
            x="카테고리", 
            y="금액", 
            color="구분", 
            barmode="group",
            text_auto='.0f',
            color_discrete_sequence=["#333333", "#E50914"]
        )
        fig.update_layout(yaxis_title="금액 (원)", xaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

        # 동종업계 상위 10개 기업 리스트
        st.subheader(f"🏆 동종업계({info['업종코드명']}) 연봉 상위 10위")
        df = data.get_data()
        industry_top10 = (
            df.loc[df['업종코드'] == info['업종코드'], ['사업장명', '월급여추정', '연간급여추정', '가입자수']]
            .sort_values('연간급여추정', ascending=False)
            .head(10)
            .reset_index(drop=True)
        )
        # 인덱스를 1부터 시작하도록 조정합니다.
        industry_top10.index = industry_top10.index + 1
        st.dataframe(industry_top10.style.format("{:,.0f}", subset=['월급여추정', '연간급여추정', '가입자수']), use_container_width=True)
            
    else:
        st.warning("입력하신 조건에 맞는 기업 데이터를 찾을 수 없습니다.")
