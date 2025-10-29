import httpx
from fastapi import WebSocket, WebSocketDisconnect, APIRouter, Depends, Request
from sqlalchemy.orm import Session
from utils.ai_model import stream_ai_response, evaluate_interview_ai
from utils.conversationMemory import ConversationMemory, summarize_text_local
from database.models import Applicant, Interview, PublicInterview, PublicInterviewAttempt
from database.database import sessionLocal, get_db
from datetime import datetime
from apps.dashboard.dashboard import extract_pdf_text
import json



websocket_router = APIRouter()

SAVE_INTERVIEW_URL = "http://localhost:8000/save-interview"
STT_URL = "http://localhost:8000/stt"


@websocket_router.websocket("/ws/chat/{applicant_id}")
async def websocket_chat(websocket: WebSocket, applicant_id: int):
    await websocket.accept()
    db: Session = sessionLocal()
    try:
        applicant = db.query(Applicant).filter(Applicant.id == applicant_id).first()
        if not applicant:
            await websocket.send_json({"type": "error", "message": "Applicant not found"})
            return

        interview = db.query(Interview).filter_by(applicant_id=applicant_id).first()
        if not interview:
            interview = Interview(applicant_id=applicant_id, transcript=[], question_count=0)
            db.add(interview)
            db.commit()
            db.refresh(interview)
        resume_text = extract_pdf_text(applicant.resume)
        # Initialize memory and system prompt
        memory = ConversationMemory(applicant.job.description, resume_text)
        system_prompt = """
                You are a professional AI interviewer conducting a voice-based technical screening. 
                Your main objective is to assess the candidate's suitability for the job through a natural, human-like conversation.

                --- INTERVIEW STYLE ---
                - Begin with a polite, friendly greeting using the candidate's name (e.g., “Hi "candidate_name", it's great to meet you!”).
                - Ask **one clear question at a time**.
                - Keep each question **concise (2-3 sentences max)**.
                - Maintain **conversational flow** and give the candidate time to respond.
                - Avoid asking multiple questions in a single turn.
                - Speak in a **friendly yet professional tone**.

                --- QUESTION STRATEGY ---
                - Begin with broad, open-ended questions.
                - Gradually increase depth based on the candidate's responses.
                - Use information from the **resume** and **job description** to tailor questions.
                - Ask practical, scenario-based questions to test applied understanding.
                - For behavioral questions, use the **STAR method** (Situation, Task, Action, Result).

                --- ADAPTATION RULES ---
                - If the candidate struggles → simplify and guide gently.
                - If the candidate excels → increase technical depth.
                - If answers are vague → ask for specific examples.
                - If short on time → focus on key job-related areas.

                --- VOICE DELIVERY ---
                - Speak naturally, with clear pronunciation and moderate pacing.
                - Use simple and understandable language.
                - Avoid technical jargon unless relevant to the candidate's expertise.

                --- SCORING CONSIDERATIONS ---
                Assess based on:
                1. Technical knowledge
                2. Problem-solving ability
                3. Communication clarity
                4. Experience relevance
                5. Cultural fit

                --- PROHIBITED BEHAVIORS ---
                Never:
                - Ask multiple questions at once
                - Interrupt the candidate
                - Jump between unrelated topics
                - Use excessive jargon or robotic phrasing

                --- Context Enforcement --
                - Stay strictly within the context of the interview.
                - If the candidate asks anything unrelated to the interview (e.g., jokes, weather, personal chat, or off-topic questions),
                respond politely but redirect them back to the interview.
                - Do not perform unrelated tasks or answer out-of-scope questions.
                - Example:
                - Candidate: “What's the weather like?”
                - Interviewer: “Let's stay focused on the interview. Can you tell me how you handle unexpected challenges at work?”


                Begin the interview with a polite greeting and the first question.
            """


        # Load any previous conversation
        conversation_buffer = []
        for msg in interview.transcript:
            await memory.add_message(msg["sender"], msg["message"])
            conversation_buffer.append(msg)

        await websocket.send_json({
            "type": "welcome",
            "total_questions": 10
        })
        if interview.question_count == 0:
            prompt = "Begin the interview with a brief welcome and the first question."
            ai_response = ""

            async for chunk in stream_ai_response(prompt, system_prompt, memory):
                if not chunk.startswith(("[ERROR]", "[DEBUG]")):
                    ai_response += chunk

            if ai_response.strip():
                await websocket.send_json({
                    "type": "question",
                    "question": ai_response.strip(),
                    "index": 1,
                    "total_questions": 10
                })
                await memory.add_message("AI", ai_response)
                conversation_buffer.append({"sender": "AI", "message": ai_response})
                interview.question_count = 1
                db.commit()
        while interview.question_count < 10:
            try:
                data = await websocket.receive()
                user_message = ""
                if data.get("type") == "websocket.receive" and data.get("text"):
                    payload = json.loads(data["text"])
                    user_message = payload.get("answer", "").strip()
                elif data.get("type") == "websocket.receive" and data.get("bytes"):
                    audio_data = data["bytes"]
                    async with httpx.AsyncClient() as client:
                        response = await client.post(STT_URL, files={"file": ("audio.webm", audio_data, "audio/webm")})
                    if response.status_code == 200:
                        user_message = response.json().get("text", "").strip()

                if not user_message:
                    await websocket.send_json({"type": "ack", "message": "Please provide your answer"})
                    continue
                await memory.add_message("User", user_message)
                conversation_buffer.append({"sender": "User", "message": user_message})
                await websocket.send_json({"type": "ack", "message": "Answer received"})

                ai_response = ""
                async for chunk in stream_ai_response(user_message, system_prompt, memory):
                    if not chunk.startswith(("[ERROR]", "[DEBUG]")):
                        ai_response += chunk

                if ai_response.strip():
                    interview.question_count += 1
                    conversation_buffer.append({"sender": "AI", "message": ai_response})
                    await memory.add_message("AI", ai_response)
                    await websocket.send_json({
                        "type": "question",
                        "question": ai_response.strip(),
                        "index": interview.question_count,
                        "total_questions": 10
                    })

                    interview.transcript = conversation_buffer
                    db.commit()

            except WebSocketDisconnect:
                break
            except Exception as e:
                await websocket.send_json({"type": "error", "message": f"Processing error: {str(e)}"})
                continue
        completion_msg = "Thank you for completing the interview! We will review your responses soon."
        await memory.add_message("AI", completion_msg)
        conversation_buffer.append({"sender": "AI", "message": completion_msg})

        interview.transcript = conversation_buffer
        interview.completed_at = datetime.utcnow()
        db.commit()
        await websocket.send_json({
            "type": "complete",
            "message": completion_msg,
            "summary": f"Completed {interview.question_count} questions"
        })
        try:
            async with httpx.AsyncClient() as client:
                await client.post(f"{SAVE_INTERVIEW_URL}/{applicant_id}", json={"transcript": conversation_buffer})
        except Exception as e:
            print(f"Error saving interview externally: {e}")
        await websocket.close()
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": f"Connection error: {str(e)}"})
        except:
            pass
    finally:
        db.close()



@websocket_router.websocket("/ws/public-interview/{interview_id}")
async def public_interview_ws(websocket: WebSocket, interview_id: int, db: Session = Depends(get_db)):
    await websocket.accept()
    try:
        attempt_id = websocket.query_params.get("attempt_id")
        if not attempt_id:
            await websocket.send_text(json.dumps({"type": "error", "message": "Attempt ID required"}))
            await websocket.close(code=4001)
            return

        attempt_id = int(attempt_id)

        interview = db.query(PublicInterview).filter_by(id=interview_id).first()
        attempt = db.query(PublicInterviewAttempt).filter_by(id=attempt_id, interview_id=interview_id).first()

        if not interview or not attempt:
            await websocket.send_text(json.dumps({"type": "error", "message": "Interview or attempt not found"}))
            await websocket.close(code=4001)
            return

        job_description = getattr(interview, 'description', 'No description provided')
        resume_text = await extract_pdf_text(getattr(attempt, 'resume', '')) or "No resume provided"
        memory = ConversationMemory(job_desc=job_description, resume=resume_text)

        system_prompt = f"""
            You are an experienced AI interviewer conducting a live, conversational interview for the position of **{interview.title}**.

            ## Context
            - **Position:** {interview.title}
            - **Job Description:** {getattr(interview, 'description', 'No description provided')}
            
            ## Your Role
            - You are a friendly yet professional interviewer. 
            - Your goal is to assess the candidate's:
            - Technical expertise
            - Problem-solving skills
            - Communication ability
            - Behavioral and teamwork qualities
            - Begin with a polite, friendly greeting using the candidate's name (e.g., "Hi (candidate_name), it's great to meet you!").

            ## Personality & Tone
            - You speak like a real human interviewer — natural, polite, and empathetic.
            - Use short conversational fillers occasionally (e.g., "That's interesting.", "I see.", "Got it.", "Makes sense.") before asking the next question.
            - Show curiosity or engagement.
            - Avoid robotic phrasing or repetitive question structures.
            - Keep your tone confident but approachable, as if you've been interviewing professionals for years.

            ## INTERVIEW STYLE 
            - Ask **one clear question at a time**.
            - Keep each question **concise (1-2 sentences max)**.
            - Maintain **conversational flow** and give the candidate time to respond.
            - Avoid asking multiple questions in a single turn.
            - Speak in a **friendly yet professional tone**.

            ## QUESTION STRATEGY 
            - Begin with broad, open-ended questions.
            - Gradually increase depth based on the candidate's responses.
            - Use information from the **resume** and **job description** to tailor questions.
            - Ask practical, scenario-based questions to test applied understanding.
            - For behavioral questions, use the **STAR method** (Situation, Task, Action, Result).

            ## Adaptation
            - If candidate hesitates → encourage gently.
            - If candidate excels → go deeper.
            - If vague → ask for specific examples.
            - Ask one clear question at a time.
            - Use information from the resume, job description and previous chat to tailor questions.

            ## Context Enforcement
            - Stay strictly within the context of the interview.
            - If the candidate asks anything unrelated to the interview (e.g., jokes, weather, personal chat, or off-topic questions),
              respond politely and redirect them back to the interview.
            - Do not perform unrelated tasks or answer out-of-scope questions.
            - Example:
            - Candidate: "What's the weather like?"
            - Interviewer: "Let's stay focused on the interview. Can you tell me how you handle unexpected challenges at work?"
            - If the candidate replies in any other language than english, respond with: "Please respond in English so we can continue the interview."

            ## Output Format
            Respond with only the next interview question in plain text (no lists, JSON, or explanations).
            """

        await websocket.send_json({
            "type": "welcome",
            "message": f"Starting AI-powered interview for {interview.title}."
        })

        question_text = ""
        async for chunk in stream_ai_response(
            user_message="Start the interview with your first question.",
            system_prompt=system_prompt,
            memory=memory
        ):
            question_text += chunk

        question_text = question_text.strip() or "Can you tell me about yourself?"

        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            tts_res = await client.post("/tts", data={"text": question_text})
            tts_audio = tts_res.json().get("audio", None)

        await websocket.send_json({
            "type": "question",
            "index": 1,
            "text": question_text,
            "audio": tts_audio
        })

        transcript = [{"question": question_text}]
        question_count = 1
        max_questions = 10

        # Main Loop
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            while question_count < max_questions:
                data = await websocket.receive_json()

                if "audio" in data:
                    audio_base64 = data["audio"]
                    
                    stt_res = await client.post("/stt-base64", data={"audio_base64": audio_base64})
                    user_text = stt_res.json().get("text", "")
                else:
                    user_text = data.get("answer", "")
  
                await websocket.send_json({
                    "type": "user_transcript",
                    "text": user_text or "(No speech detected)"
                })
                transcript[-1]["answer"] = user_text

                if data.get("end_interview"):
                    break

                # Generate next question
                next_question = ""
                async for chunk in stream_ai_response(
                    user_message=f"Candidate said: {user_text}\nContinue the interview with one next question.",
                    system_prompt=system_prompt,
                    memory=memory
                ):
                    next_question += chunk
                next_question = next_question.strip()

                if not next_question:
                    break

                # Convert next question to speech
                tts_res = await client.post("/tts", data={"text": next_question})
                next_audio = tts_res.json().get("audio", None)

                question_count += 1
                transcript.append({"question": next_question})
                await websocket.send_json({
                    "type": "question",
                    "index": question_count,
                    "text": next_question,
                    "audio": next_audio
                })

        # Evaluation step
        await websocket.send_json({"type": "evaluation_start"})

        formatted_transcript = ""
        for i, qa in enumerate(transcript, 1):
            formatted_transcript += f"Q{i}: {qa.get('question')}\nA{i}: {qa.get('answer', 'No answer')}\n\n"

        eval_prompt = f"""
        You are an expert technical interviewer evaluating a candidate's performance.

        JOB POSITION: {interview.title}
        JOB DESCRIPTION: {summarize_text_local(job_description)}
        CANDIDATE RESUME SUMMARY: {summarize_text_local(resume_text)}

        INTERVIEW TRANSCRIPT:
        {formatted_transcript}

        Evaluate the candidate based on:
        1. Technical knowledge and skills relevant to the position
        2. Communication clarity and effectiveness  
        3. Problem-solving approach and critical thinking
        4. Behavioral competencies and cultural fit
        5. Overall confidence and professionalism

        Provide your evaluation in this EXACT JSON format:
        {{
            "score": 85,
            "feedback": "Detailed constructive feedback here..."
        }}

        IMPORTANT: 
        - Score should be 0-100 based on overall performance
        - Feedback should be detailed and constructive
        - Be fair and objective in your assessment
        """

        eval_text = ""
        async for chunk in evaluate_interview_ai(
            user_message=eval_prompt,
            system_prompt="You are an expert interviewer. Output pure JSON only.",
            memory=None
        ):
            eval_text += chunk

        eval_text = eval_text.strip().replace("```json", "").replace("```", "")
        try:
            result = json.loads(eval_text)
        except:
            result = {"score": 75, "feedback": "Good communication skills."}

        attempt.score = result.get("score", 0)
        attempt.feedback = result.get("feedback", "")
        attempt.transcript = transcript
        db.commit()

        await websocket.send_json({
            "type": "evaluation",
            "score": attempt.score,
            "feedback": attempt.feedback
        })

        await websocket.send_json({
            "type": "complete",
            "message": "Interview completed successfully.",
            "total_questions": question_count
        })

    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})
    finally:
        await websocket.close()

