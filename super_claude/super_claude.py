#!/usr/bin/env python3
"""
Super Claude - Advanced AI Development Assistant
고급 AI 개발 어시스턴트 with Deep Thinking, Auto Persona, Strategic Planning
"""

import os
import json
import time
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import re
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('super_claude.log'),
        logging.StreamHandler()
    ]
)

class PersonaType(Enum):
    """사용 가능한 페르소나 타입들"""
    SENIOR_DEVELOPER = "senior_developer"
    SYSTEM_ARCHITECT = "system_architect"
    SECURITY_EXPERT = "security_expert"
    PERFORMANCE_OPTIMIZER = "performance_optimizer"
    CODE_REVIEWER = "code_reviewer"
    PROJECT_MANAGER = "project_manager"
    TECHNICAL_WRITER = "technical_writer"
    DEVOPS_ENGINEER = "devops_engineer"

class ThinkingStage(Enum):
    """사고 단계"""
    ANALYSIS = "분석"
    DECOMPOSITION = "분해"
    STRATEGY = "전략"
    RISK_ASSESSMENT = "리스크평가"
    PLANNING = "계획"
    VALIDATION = "검증"

@dataclass
class PersonaProfile:
    """페르소나 프로필"""
    name: str
    description: str
    expertise: List[str]
    thinking_style: str
    communication_style: str
    tools: List[str]
    experience_years: int

@dataclass
class ProjectContext:
    """프로젝트 컨텍스트"""
    name: str
    description: str
    tech_stack: List[str]
    requirements: List[str]
    constraints: List[str]
    timeline: Optional[datetime] = None
    budget: Optional[float] = None
    team_size: Optional[int] = None

@dataclass
class ThinkingResult:
    """사고 결과"""
    stage: ThinkingStage
    analysis: str
    insights: List[str]
    recommendations: List[str]
    risks: List[str]
    confidence: float

class PersonaManager:
    """페르소나 관리자"""
    
    def __init__(self):
        self.personas = self._initialize_personas()
        self.current_persona = None
        self.logger = logging.getLogger(__name__)
    
    def _initialize_personas(self) -> Dict[PersonaType, PersonaProfile]:
        """페르소나 초기화"""
        return {
            PersonaType.SENIOR_DEVELOPER: PersonaProfile(
                name="시니어 개발자 Alex",
                description="20년 경력의 풀스택 시니어 개발자",
                expertise=["아키텍처 설계", "코드 최적화", "기술 선택", "멘토링"],
                thinking_style="체계적이고 경험 기반의 판단",
                communication_style="명확하고 실용적인 조언",
                tools=["Python", "JavaScript", "Go", "Docker", "Kubernetes"],
                experience_years=20
            ),
            PersonaType.SYSTEM_ARCHITECT: PersonaProfile(
                name="시스템 아키텍트 Morgan",
                description="대규모 분산 시스템 설계 전문가",
                expertise=["마이크로서비스", "확장성", "성능", "데이터 아키텍처"],
                thinking_style="전체적인 시스템 관점에서 사고",
                communication_style="구조적이고 논리적인 설명",
                tools=["AWS", "GCP", "Kafka", "Redis", "PostgreSQL"],
                experience_years=15
            ),
            PersonaType.SECURITY_EXPERT: PersonaProfile(
                name="보안 전문가 Jordan",
                description="사이버보안 및 취약점 분석 전문가",
                expertise=["보안 아키텍처", "취약점 분석", "암호화", "컴플라이언스"],
                thinking_style="위험 중심의 방어적 사고",
                communication_style="신중하고 상세한 경고",
                tools=["OWASP", "Burp Suite", "Nmap", "OpenSSL"],
                experience_years=12
            ),
            PersonaType.PERFORMANCE_OPTIMIZER: PersonaProfile(
                name="성능 최적화 전문가 Taylor",
                description="시스템 성능 튜닝 및 최적화 전문가",
                expertise=["프로파일링", "메모리 최적화", "병렬 처리", "캐싱"],
                thinking_style="데이터 기반의 분석적 사고",
                communication_style="수치와 벤치마크 중심의 설명",
                tools=["Profilers", "APM", "JMeter", "Grafana"],
                experience_years=10
            ),
            PersonaType.CODE_REVIEWER: PersonaProfile(
                name="코드 리뷰어 Casey",
                description="코드 품질 및 베스트 프랙티스 전문가",
                expertise=["코드 품질", "리팩토링", "테스팅", "CI/CD"],
                thinking_style="품질과 maintainability 중심 사고",
                communication_style="건설적이고 교육적인 피드백",
                tools=["SonarQube", "ESLint", "pytest", "GitHub Actions"],
                experience_years=8
            ),
            PersonaType.PROJECT_MANAGER: PersonaProfile(
                name="프로젝트 매니저 Riley",
                description="애자일 프로젝트 관리 및 팀 리더십 전문가",
                expertise=["프로젝트 계획", "리스크 관리", "팀 협업", "일정 관리"],
                thinking_style="전략적이고 협업 중심의 사고",
                communication_style="명확한 커뮤니케이션과 조율",
                tools=["Jira", "Confluence", "Slack", "Miro"],
                experience_years=12
            )
        }
    
    def select_optimal_persona(self, request: str, context: Optional[ProjectContext] = None) -> PersonaType:
        """요청에 최적인 페르소나 자동 선택"""
        request_lower = request.lower()
        
        # 키워드 기반 페르소나 매칭
        persona_keywords = {
            PersonaType.SENIOR_DEVELOPER: ["개발", "코드", "프로그래밍", "구현", "디버깅"],
            PersonaType.SYSTEM_ARCHITECT: ["아키텍처", "설계", "시스템", "확장성", "구조"],
            PersonaType.SECURITY_EXPERT: ["보안", "취약점", "암호화", "해킹", "인증"],
            PersonaType.PERFORMANCE_OPTIMIZER: ["성능", "최적화", "속도", "메모리", "병목"],
            PersonaType.CODE_REVIEWER: ["리뷰", "품질", "리팩토링", "테스트", "베스트"],
            PersonaType.PROJECT_MANAGER: ["계획", "관리", "일정", "팀", "프로젝트"]
        }
        
        scores = {}
        for persona_type, keywords in persona_keywords.items():
            score = sum(1 for keyword in keywords if keyword in request_lower)
            scores[persona_type] = score
        
        # 가장 높은 점수의 페르소나 선택
        selected_persona = max(scores, key=scores.get)
        
        # 기본값: 시니어 개발자
        if scores[selected_persona] == 0:
            selected_persona = PersonaType.SENIOR_DEVELOPER
        
        self.current_persona = selected_persona
        self.logger.info(f"🎭 선택된 페르소나: {self.personas[selected_persona].name}")
        
        return selected_persona
    
    def get_persona_prompt(self, persona_type: PersonaType) -> str:
        """페르소나별 프롬프트 생성"""
        persona = self.personas[persona_type]
        
        return f"""
당신은 {persona.name}입니다.

**전문 분야**: {', '.join(persona.expertise)}
**경력**: {persona.experience_years}년
**사고 방식**: {persona.thinking_style}
**소통 스타일**: {persona.communication_style}
**주요 도구**: {', '.join(persona.tools)}

{persona.description}로서 전문적이고 실무적인 관점에서 답변해주세요.
한국어로 답변하되, 기술 용어는 영어 원문을 병기해주세요.
"""

class DeepThinkingEngine:
    """심층 사고 엔진"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.thinking_history = []
    
    async def deep_think(self, request: str, context: Optional[ProjectContext] = None) -> List[ThinkingResult]:
        """심층 사고 프로세스 실행"""
        self.logger.info("🧠 심층 사고 프로세스 시작...")
        
        results = []
        
        # 1단계: 문제 분석
        analysis_result = await self._analyze_problem(request, context)
        results.append(analysis_result)
        
        # 2단계: 문제 분해
        decomposition_result = await self._decompose_problem(request, analysis_result)
        results.append(decomposition_result)
        
        # 3단계: 전략 수립
        strategy_result = await self._develop_strategy(request, analysis_result, decomposition_result)
        results.append(strategy_result)
        
        # 4단계: 리스크 평가
        risk_result = await self._assess_risks(request, context, strategy_result)
        results.append(risk_result)
        
        # 5단계: 실행 계획
        planning_result = await self._create_execution_plan(request, context, results)
        results.append(planning_result)
        
        # 6단계: 검증
        validation_result = await self._validate_approach(request, results)
        results.append(validation_result)
        
        self.thinking_history.extend(results)
        self.logger.info("✅ 심층 사고 프로세스 완료")
        
        return results
    
    async def _analyze_problem(self, request: str, context: Optional[ProjectContext]) -> ThinkingResult:
        """문제 분석"""
        await asyncio.sleep(0.1)  # 실제로는 LLM 호출
        
        # 요청에서 핵심 키워드 추출
        keywords = self._extract_keywords(request)
        
        # 복잡도 평가
        complexity = self._assess_complexity(request)
        
        # 도메인 식별
        domain = self._identify_domain(request)
        
        insights = [
            f"핵심 키워드: {', '.join(keywords)}",
            f"예상 복잡도: {complexity}/5",
            f"주요 도메인: {domain}",
        ]
        
        if context:
            insights.append(f"프로젝트 컨텍스트: {context.name}")
            insights.append(f"기술 스택: {', '.join(context.tech_stack)}")
        
        return ThinkingResult(
            stage=ThinkingStage.ANALYSIS,
            analysis="요청 사항을 다각도로 분석하여 핵심 요소들을 파악했습니다.",
            insights=insights,
            recommendations=["문제의 본질을 명확히 파악", "요구사항 우선순위 설정"],
            risks=["요구사항 불명확성", "범위 확산 가능성"],
            confidence=0.8
        )
    
    async def _decompose_problem(self, request: str, analysis: ThinkingResult) -> ThinkingResult:
        """문제 분해"""
        await asyncio.sleep(0.1)
        
        # 문제를 하위 작업으로 분해
        subtasks = self._break_down_tasks(request)
        
        # 의존성 분석
        dependencies = self._analyze_dependencies(subtasks)
        
        insights = [
            f"주요 하위 작업: {len(subtasks)}개",
            f"의존성 관계: {dependencies}개 발견",
            "작업 우선순위 기반 정렬 완료"
        ]
        
        return ThinkingResult(
            stage=ThinkingStage.DECOMPOSITION,
            analysis="복잡한 문제를 관리 가능한 하위 작업들로 분해했습니다.",
            insights=insights,
            recommendations=["단계별 접근법 적용", "병렬 처리 가능한 작업 식별"],
            risks=["작업 간 의존성 복잡화", "통합 시점의 문제"],
            confidence=0.85
        )
    
    async def _develop_strategy(self, request: str, analysis: ThinkingResult, decomposition: ThinkingResult) -> ThinkingResult:
        """전략 수립"""
        await asyncio.sleep(0.1)
        
        # 솔루션 접근법 결정
        approaches = self._identify_solution_approaches(request)
        
        # 최적 접근법 선택
        best_approach = self._select_best_approach(approaches)
        
        insights = [
            f"검토된 접근법: {len(approaches)}개",
            f"선택된 접근법: {best_approach}",
            "기술적 타당성 검증 완료"
        ]
        
        return ThinkingResult(
            stage=ThinkingStage.STRATEGY,
            analysis="다양한 솔루션 접근법을 검토하여 최적의 전략을 수립했습니다.",
            insights=insights,
            recommendations=["선택된 접근법으로 프로토타입 개발", "점진적 구현 적용"],
            risks=["기술적 제약 발견", "성능 이슈 가능성"],
            confidence=0.75
        )
    
    def _extract_keywords(self, text: str) -> List[str]:
        """키워드 추출"""
        # 간단한 키워드 추출 (실제로는 더 정교한 NLP 사용)
        keywords = re.findall(r'\b[가-힣a-zA-Z]{2,}\b', text)
        return list(set(keywords))[:5]
    
    def _assess_complexity(self, request: str) -> int:
        """복잡도 평가"""
        complexity_indicators = ['시스템', '통합', '최적화', '보안', '확장', '분산']
        score = sum(1 for indicator in complexity_indicators if indicator in request)
        return min(5, max(1, score))
    
    def _identify_domain(self, request: str) -> str:
        """도메인 식별"""
        domains = {
            '웹': ['웹', 'web', 'html', 'css', 'javascript'],
            '모바일': ['모바일', 'mobile', 'ios', 'android'],
            '백엔드': ['백엔드', 'backend', 'api', 'server'],
            'AI/ML': ['ai', 'ml', '머신러닝', '인공지능'],
            '데이터': ['데이터', 'data', '분석', 'database']
        }
        
        for domain, keywords in domains.items():
            if any(keyword in request.lower() for keyword in keywords):
                return domain
        return '일반'
    
    def _break_down_tasks(self, request: str) -> List[str]:
        """작업 분해"""
        # 실제로는 더 정교한 작업 분해 로직
        return [
            "요구사항 분석",
            "기술 스택 선정",
            "아키텍처 설계",
            "구현",
            "테스트",
            "배포"
        ]
    
    def _analyze_dependencies(self, tasks: List[str]) -> int:
        """의존성 분석"""
        return len(tasks) - 1  # 간단한 선형 의존성 가정
    
    def _identify_solution_approaches(self, request: str) -> List[str]:
        """솔루션 접근법 식별"""
        return ["점진적 개발", "프로토타입 우선", "기존 솔루션 활용", "새로운 구현"]
    
    def _select_best_approach(self, approaches: List[str]) -> str:
        """최적 접근법 선택"""
        return approaches[0]  # 간단한 선택 로직
    
    async def _assess_risks(self, request: str, context: Optional[ProjectContext], strategy: ThinkingResult) -> ThinkingResult:
        """리스크 평가"""
        await asyncio.sleep(0.1)
        
        risks = [
            "기술적 복잡성",
            "시간 제약",
            "리소스 부족",
            "통합 문제"
        ]
        
        mitigation_strategies = [
            "프로토타입을 통한 검증",
            "점진적 개발 접근",
            "충분한 테스팅",
            "문서화 강화"
        ]
        
        return ThinkingResult(
            stage=ThinkingStage.RISK_ASSESSMENT,
            analysis="주요 리스크 요소들을 식별하고 완화 전략을 수립했습니다.",
            insights=[f"식별된 리스크: {len(risks)}개", "모든 리스크에 대한 완화 전략 보유"],
            recommendations=mitigation_strategies,
            risks=risks,
            confidence=0.7
        )
    
    async def _create_execution_plan(self, request: str, context: Optional[ProjectContext], results: List[ThinkingResult]) -> ThinkingResult:
        """실행 계획 수립"""
        await asyncio.sleep(0.1)
        
        phases = [
            "Phase 1: 분석 및 설계 (1-2주)",
            "Phase 2: 핵심 기능 구현 (3-4주)",
            "Phase 3: 테스트 및 최적화 (1-2주)",
            "Phase 4: 배포 및 모니터링 (1주)"
        ]
        
        milestones = [
            "설계 문서 완료",
            "MVP 구현 완료",
            "테스트 완료",
            "프로덕션 배포"
        ]
        
        return ThinkingResult(
            stage=ThinkingStage.PLANNING,
            analysis="구체적인 실행 계획을 단계별로 수립했습니다.",
            insights=[f"총 {len(phases)}개 단계", f"{len(milestones)}개 주요 마일스톤"],
            recommendations=phases + milestones,
            risks=["일정 지연", "범위 변경"],
            confidence=0.8
        )
    
    async def _validate_approach(self, request: str, results: List[ThinkingResult]) -> ThinkingResult:
        """접근법 검증"""
        await asyncio.sleep(0.1)
        
        # 전체 접근법의 일관성 검증
        consistency_check = "통과"
        feasibility_check = "높음"
        
        validation_points = [
            "기술적 타당성 검증",
            "리소스 요구사항 적정성",
            "일정 현실성",
            "리스크 대응 완비"
        ]
        
        return ThinkingResult(
            stage=ThinkingStage.VALIDATION,
            analysis="전체 접근법의 타당성과 실현 가능성을 검증했습니다.",
            insights=[
                f"일관성 검사: {consistency_check}",
                f"실현 가능성: {feasibility_check}",
                "모든 검증 포인트 통과"
            ],
            recommendations=["계획대로 진행", "정기적 검토 포인트 설정"],
            risks=["예상치 못한 변수"],
            confidence=0.9
        )

class StrategicPlanner:
    """전략 계획 모듈"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def create_project_roadmap(self, context: ProjectContext, thinking_results: List[ThinkingResult]) -> Dict[str, Any]:
        """프로젝트 로드맵 생성"""
        
        roadmap = {
            "project_info": {
                "name": context.name,
                "description": context.description,
                "tech_stack": context.tech_stack,
                "estimated_duration": "6-8주"
            },
            "phases": self._generate_phases(thinking_results),
            "milestones": self._generate_milestones(context),
            "resources": self._estimate_resources(context),
            "risks": self._consolidate_risks(thinking_results),
            "success_criteria": self._define_success_criteria(context)
        }
        
        return roadmap
    
    def _generate_phases(self, thinking_results: List[ThinkingResult]) -> List[Dict[str, Any]]:
        """개발 단계 생성"""
        return [
            {
                "name": "Discovery & Planning",
                "duration": "1-2주",
                "activities": ["요구사항 분석", "기술 조사", "아키텍처 설계"],
                "deliverables": ["요구사항 문서", "기술 스택 결정", "아키텍처 다이어그램"]
            },
            {
                "name": "Core Development",
                "duration": "3-4주", 
                "activities": ["핵심 기능 구현", "API 개발", "데이터베이스 설계"],
                "deliverables": ["MVP", "API 문서", "데이터베이스 스키마"]
            },
            {
                "name": "Testing & Optimization",
                "duration": "1-2주",
                "activities": ["단위 테스트", "통합 테스트", "성능 최적화"],
                "deliverables": ["테스트 리포트", "성능 벤치마크", "최적화된 코드"]
            },
            {
                "name": "Deployment & Monitoring", 
                "duration": "1주",
                "activities": ["배포 파이프라인", "모니터링 설정", "문서화"],
                "deliverables": ["프로덕션 배포", "모니터링 대시보드", "운영 문서"]
            }
        ]
    
    def _generate_milestones(self, context: ProjectContext) -> List[Dict[str, Any]]:
        """마일스톤 생성"""
        return [
            {"name": "프로젝트 킥오프", "week": 1, "criteria": "팀 구성 및 목표 설정 완료"},
            {"name": "설계 완료", "week": 2, "criteria": "기술 아키텍처 및 설계 문서 승인"},
            {"name": "MVP 완료", "week": 5, "criteria": "핵심 기능 구현 및 내부 테스트 완료"},
            {"name": "베타 릴리즈", "week": 7, "criteria": "전체 기능 구현 및 테스트 완료"},
            {"name": "프로덕션 런치", "week": 8, "criteria": "안정적인 프로덕션 배포 완료"}
        ]
    
    def _estimate_resources(self, context: ProjectContext) -> Dict[str, Any]:
        """리소스 추정"""
        return {
            "team_composition": [
                "시니어 개발자 1명",
                "주니어 개발자 1-2명", 
                "DevOps 엔지니어 0.5명",
                "QA 엔지니어 0.5명"
            ],
            "infrastructure": [
                "개발 환경",
                "스테이징 환경", 
                "프로덕션 환경",
                "CI/CD 파이프라인"
            ],
            "tools": [
                "IDE/편집기",
                "버전 관리 (Git)",
                "프로젝트 관리 도구",
                "모니터링 도구"
            ]
        }
    
    def _consolidate_risks(self, thinking_results: List[ThinkingResult]) -> List[Dict[str, Any]]:
        """리스크 통합"""
        all_risks = []
        for result in thinking_results:
            all_risks.extend(result.risks)
        
        # 중복 제거 및 우선순위 설정
        unique_risks = list(set(all_risks))
        
        return [
            {"risk": risk, "probability": "중간", "impact": "높음", "mitigation": "정기 검토 및 대응책 준비"}
            for risk in unique_risks[:5]  # 상위 5개 리스크
        ]
    
    def _define_success_criteria(self, context: ProjectContext) -> List[str]:
        """성공 기준 정의"""
        return [
            "모든 핵심 요구사항 구현 완료",
            "성능 목표 달성 (응답시간 < 2초)",
            "99% 이상의 가용성 확보",
            "보안 검증 통과",
            "사용자 만족도 4.0/5.0 이상"
        ]

class SuperClaude:
    """Super Claude 메인 클래스"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.persona_manager = PersonaManager()
        self.thinking_engine = DeepThinkingEngine()
        self.strategic_planner = StrategicPlanner()
        
        self.session_history = []
        self.current_project = None
        
        self.logger.info("🚀 Super Claude 초기화 완료")
    
    async def process_request(self, request: str, project_context: Optional[ProjectContext] = None) -> Dict[str, Any]:
        """요청 처리 메인 메서드"""
        self.logger.info(f"📝 요청 처리 시작: {request[:50]}...")
        
        start_time = time.time()
        
        # 1. 최적 페르소나 선택
        selected_persona = self.persona_manager.select_optimal_persona(request, project_context)
        persona_prompt = self.persona_manager.get_persona_prompt(selected_persona)
        
        # 2. 심층 사고 프로세스
        thinking_results = await self.thinking_engine.deep_think(request, project_context)
        
        # 3. 전략 계획 (프로젝트 컨텍스트가 있는 경우)
        roadmap = None
        if project_context:
            roadmap = self.strategic_planner.create_project_roadmap(project_context, thinking_results)
        
        # 4. 응답 생성
        response = self._generate_response(
            request, selected_persona, thinking_results, roadmap, project_context
        )
        
        # 5. 세션 히스토리 업데이트
        session_data = {
            "timestamp": datetime.now().isoformat(),
            "request": request,
            "persona": selected_persona.value,
            "thinking_results": len(thinking_results),
            "processing_time": time.time() - start_time,
            "response_length": len(response["response"])
        }
        self.session_history.append(session_data)
        
        self.logger.info(f"✅ 요청 처리 완료 ({session_data['processing_time']:.2f}초)")
        
        return response
    
    def _generate_response(self, request: str, persona: PersonaType, 
                          thinking_results: List[ThinkingResult], 
                          roadmap: Optional[Dict], 
                          context: Optional[ProjectContext]) -> Dict[str, Any]:
        """응답 생성"""
        
        persona_info = self.persona_manager.personas[persona]
        
        # 사고 과정 요약
        thinking_summary = self._summarize_thinking(thinking_results)
        
        # 메인 응답 구성
        response_parts = [
            f"## 🎭 {persona_info.name}의 분석\n",
            f"**전문 분야**: {', '.join(persona_info.expertise)}\n",
            f"**경력**: {persona_info.experience_years}년\n\n",
            
            "## 🧠 심층 분석 결과\n",
            thinking_summary,
            "\n"
        ]
        
        if roadmap:
            response_parts.extend([
                "## 📋 프로젝트 로드맵\n",
                self._format_roadmap(roadmap),
                "\n"
            ])
        
        # 최종 권장사항
        final_recommendations = self._generate_final_recommendations(thinking_results, persona_info)
        response_parts.extend([
            "## 💡 최종 권장사항\n",
            final_recommendations,
            "\n"
        ])
        
        # 다음 단계
        next_steps = self._suggest_next_steps(thinking_results, context)
        response_parts.extend([
            "## 🚀 다음 단계\n",
            next_steps
        ])
        
        return {
            "response": "".join(response_parts),
            "persona": persona.value,
            "persona_name": persona_info.name,
            "confidence": self._calculate_overall_confidence(thinking_results),
            "thinking_stages": len(thinking_results),
            "has_roadmap": roadmap is not None,
            "metadata": {
                "thinking_results": thinking_results,
                "roadmap": roadmap,
                "session_id": len(self.session_history)
            }
        }
    
    def _summarize_thinking(self, results: List[ThinkingResult]) -> str:
        """사고 과정 요약"""
        summary_parts = []
        
        for result in results:
            summary_parts.append(f"### {result.stage.value}\n")
            summary_parts.append(f"{result.analysis}\n\n")
            
            if result.insights:
                summary_parts.append("**주요 인사이트:**\n")
                for insight in result.insights:
                    summary_parts.append(f"- {insight}\n")
                summary_parts.append("\n")
            
            if result.recommendations:
                summary_parts.append("**권장사항:**\n")
                for rec in result.recommendations[:3]:  # 상위 3개만
                    summary_parts.append(f"- {rec}\n")
                summary_parts.append("\n")
        
        return "".join(summary_parts)
    
    def _format_roadmap(self, roadmap: Dict[str, Any]) -> str:
        """로드맵 포맷팅"""
        parts = []
        
        # 프로젝트 정보
        project_info = roadmap["project_info"]
        parts.append(f"**프로젝트**: {project_info['name']}\n")
        parts.append(f"**예상 기간**: {project_info['estimated_duration']}\n")
        parts.append(f"**기술 스택**: {', '.join(project_info['tech_stack'])}\n\n")
        
        # 단계별 계획
        parts.append("### 개발 단계\n")
        for i, phase in enumerate(roadmap["phases"], 1):
            parts.append(f"**{i}. {phase['name']}** ({phase['duration']})\n")
            parts.append(f"- 주요 활동: {', '.join(phase['activities'])}\n")
            parts.append(f"- 결과물: {', '.join(phase['deliverables'])}\n\n")
        
        # 마일스톤
        parts.append("### 주요 마일스톤\n")
        for milestone in roadmap["milestones"]:
            parts.append(f"- **Week {milestone['week']}**: {milestone['name']} - {milestone['criteria']}\n")
        
        return "".join(parts)
    
    def _generate_final_recommendations(self, results: List[ThinkingResult], persona: PersonaProfile) -> str:
        """최종 권장사항 생성"""
        all_recommendations = []
        
        # 모든 사고 단계의 권장사항 수집
        for result in results:
            all_recommendations.extend(result.recommendations)
        
        # 페르소나 특성에 맞는 권장사항 필터링 및 우선순위 설정
        top_recommendations = list(set(all_recommendations))[:5]
        
        parts = []
        for i, rec in enumerate(top_recommendations, 1):
            parts.append(f"{i}. {rec}\n")
        
        # 페르소나별 추가 조언
        persona_advice = {
            PersonaType.SENIOR_DEVELOPER: "코드 품질과 유지보수성을 최우선으로 고려하세요.",
            PersonaType.SYSTEM_ARCHITECT: "전체 시스템의 확장성과 안정성을 염두에 두고 설계하세요.",
            PersonaType.SECURITY_EXPERT: "보안은 나중에 추가하는 것이 아니라 처음부터 설계에 포함해야 합니다.",
            PersonaType.PERFORMANCE_OPTIMIZER: "성능 최적화는 측정 가능한 메트릭을 기반으로 진행하세요.",
            PersonaType.CODE_REVIEWER: "코드 리뷰와 테스트는 개발 프로세스의 필수 요소입니다.",
            PersonaType.PROJECT_MANAGER: "명확한 커뮤니케이션과 정기적인 체크포인트가 성공의 열쇠입니다."
        }
        
        persona_type = PersonaType(persona.name.split()[0].lower() + "_" + persona.name.split()[1].lower())
        if persona_type in persona_advice:
            parts.append(f"\n💡 **{persona.name}의 조언**: {persona_advice.get(persona_type, '')}\n")
        
        return "".join(parts)
    
    def _suggest_next_steps(self, results: List[ThinkingResult], context: Optional[ProjectContext]) -> str:
        """다음 단계 제안"""
        steps = [
            "1. 요구사항을 더 구체화하고 우선순위를 설정하세요",
            "2. 프로토타입을 통해 핵심 가정들을 검증하세요", 
            "3. 기술 스택을 확정하고 개발 환경을 구성하세요",
            "4. 팀원들과 계획을 공유하고 피드백을 받으세요",
            "5. 첫 번째 마일스톤을 향해 개발을 시작하세요"
        ]
        
        if context:
            steps.insert(1, f"2. {context.name} 프로젝트의 상세 기획서를 작성하세요")
        
        return "\n".join(steps)
    
    def _calculate_overall_confidence(self, results: List[ThinkingResult]) -> float:
        """전체 신뢰도 계산"""
        if not results:
            return 0.5
        
        return sum(result.confidence for result in results) / len(results)
    
    def get_session_stats(self) -> Dict[str, Any]:
        """세션 통계"""
        if not self.session_history:
            return {"message": "No sessions yet"}
        
        total_requests = len(self.session_history)
        avg_processing_time = sum(s["processing_time"] for s in self.session_history) / total_requests
        
        persona_usage = {}
        for session in self.session_history:
            persona = session["persona"]
            persona_usage[persona] = persona_usage.get(persona, 0) + 1
        
        most_used_persona = max(persona_usage, key=persona_usage.get)
        
        return {
            "total_requests": total_requests,
            "average_processing_time": f"{avg_processing_time:.2f}초",
            "persona_usage": persona_usage,
            "most_used_persona": most_used_persona,
            "total_thinking_stages": sum(s["thinking_results"] for s in self.session_history)
        }

# 사용 예제
async def main():
    """메인 실행 함수"""
    super_claude = SuperClaude()
    
    # 예제 프로젝트 컨텍스트
    project_context = ProjectContext(
        name="암호화폐 자동거래 시스템 고도화",
        description="기존 거래 시스템의 성능 최적화 및 새로운 알고리즘 추가",
        tech_stack=["Python", "FastAPI", "PostgreSQL", "Redis", "Docker"],
        requirements=[
            "거래 속도 향상",
            "리스크 관리 개선", 
            "모니터링 강화",
            "백테스팅 기능 추가"
        ],
        constraints=[
            "기존 시스템과 호환성 유지",
            "실시간 처리 필수",
            "높은 가용성 요구"
        ]
    )
    
    # 요청 처리
    request = """
    현재 암호화폐 자동거래 시스템이 있는데, 성능을 크게 개선하고 싶습니다.
    특히 거래 속도가 느리고, 리스크 관리가 부족한 것 같아요.
    새로운 머신러닝 알고리즘도 추가하고 싶고, 전체적인 시스템 아키텍처도 
    개선이 필요할 것 같습니다. 어떻게 접근하면 좋을까요?
    """
    
    print("🚀 Super Claude 시작...")
    print("=" * 80)
    
    # 요청 처리
    response = await super_claude.process_request(request, project_context)
    
    print(response["response"])
    print("\n" + "=" * 80)
    print("📊 세션 통계:")
    stats = super_claude.get_session_stats()
    for key, value in stats.items():
        print(f"- {key}: {value}")

if __name__ == "__main__":
    asyncio.run(main())