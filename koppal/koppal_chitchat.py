"""
chitchat.py

Reply variations for non-NYSC small talk. Each category maps to a list
of replies; get_reply() picks one at random so the bot doesn't repeat
itself. Categories and reply patterns follow conventions used in
production conversational systems (Rasa's demo bot response variations,
live-chat industry canned-response tone/length norms), written in this
bot's own voice.

These categories should exist as trained intents in your main CSV too
(answer_type = chitchat) so the classifier can route to them. This file
only holds reply text, not training examples.
"""

import random
import re
from datetime import datetime
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("Africa/Lagos")

CHITCHAT_REPLIES = {'greeting': ['Hey! What can I help you with?',
              "Hi! What's up?",
              'Hello! How can I help?',
              'Hey there — what do you need?',
              'Hi! What would you like to know?',
              "Hello! Go ahead, I'm listening.",
              'Hey! What are you looking for?',
              'Hi there! How can I assist?',
              "Hello! What's on your mind?",
              'Hey, welcome. What can I help you with?',
              'Hi! Ask me anything about NYSC.',
              'Hello there! What can I clear up for you?',
              'Hey corper! What can I help you with?',
              'How far, corper? What\'s up?',
              'Hi pal, what do you need?',
              "Hey kopa! What's on your mind?"],
 'greeting_morning': ['Good morning! What can I help you with?',
                      "Morning! What's up?",
                      'Good morning — what do you need today?',
                      'Morning! How can I help?',
                      "Good morning! What's on your mind?",
                      'Morning! Go ahead, ask away.',
                      'Good morning! What would you like to know?',
                      "Morning! I'm here. What do you need?",
                      'Good morning! How can I make things easier?',
                      'Morning! What NYSC question do you have?',
                      'Good morning! Ready when you are.',
                      'Morning! What can I clarify for you?'],
 'greeting_afternoon': ['Good afternoon! What can I help with?',
                        "Afternoon! What's up?",
                        'Good afternoon — what do you need?',
                        'Afternoon! How can I help?',
                        "Good afternoon! What's on your mind?",
                        'Afternoon! Go ahead, ask away.',
                        'Good afternoon! What would you like to know?',
                        "Afternoon! I'm here. What do you need?",
                        'Good afternoon! How can I make things easier?',
                        'Afternoon! What NYSC question do you have?',
                        'Good afternoon! Ready when you are.',
                        'Afternoon! What can I clarify for you?'],
 'greeting_evening': ['Good evening! What can I help you with?',
                      "Evening! What's up?",
                      'Good evening — what do you need?',
                      'Evening! How can I help?',
                      "Good evening! What's on your mind?",
                      'Evening! Go ahead, ask away.',
                      'Good evening! What would you like to know?',
                      "Evening! I'm here. What do you need?",
                      'Good evening! How can I make things easier?',
                      'Evening! What NYSC question do you have?',
                      'Good evening! Ready when you are.',
                      'Evening! What can I clarify for you?'],
 'greeting_night': ["Hey, up late! What can I help you with?",
                    'Hello! Burning the midnight oil? What do you need?',
                    'Hi! Night owl mode — what do you need?',
                    "Still up? I'm here, what's on your mind?",
                    "Hey! Late one tonight — go ahead, what's the question?",
                    'Hi there, night shift huh? What can I help with?'],
 'farewell': ['Take care! Come back if you need anything else.',
              'Goodbye! Hope the rest of your day goes well.',
              'Bye for now!',
              'See you later! Good luck with your service year.',
              "Take care — I'll be here if you have another question.",
              'Alright, see you around!',
              'Goodbye! Wishing you a smooth service year.',
              'Catch you later. Feel free to come back anytime.',
              'Bye! Hope everything works out.',
              'Alright, take care and good luck.',
              "See you! Don't hesitate to ask if something else comes up.",
              'Bye for now — all the best.'],
 'thanks': ["You're welcome!",
            'Anytime!',
            'Glad I could help.',
            'No problem!',
            'Happy to help.',
            'Of course!',
            "You're very welcome.",
            'No worries at all.',
            'Sure thing!',
            'Glad that helped.',
            'Absolutely — anytime.',
            "You're welcome! Good luck with everything."],
 'how_are_you': ["I'm doing well, thanks for asking! What can I help you with?",
                 "Doing good! What's on your mind?",
                 "I'm good, thanks. What do you need?",
                 'All good here! How can I help?',
                 "I'm doing fine. What can I clarify for you?",
                 'Doing alright! Go ahead with your question.',
                 "I'm good on my end. What's up?",
                 'All well here. What would you like to know?',
                 "Can't complain — I'm here and ready to help.",
                 "I'm doing great! What can I do for you?",
                 'Pretty good, thanks! What do you need today?',
                 'All good. Ask away!'],
 'mood_great': ["Nice! Glad to hear you're doing well.",
                "That's great to hear! What can I help you with?",
                'Love that! What do you need today?',
                "Good to hear! What's on your mind?",
                "That's nice! Go ahead with your question.",
                'Awesome — what can I help with?',
                'Glad things are going well for you!',
                "That's good news. What would you like to know?",
                'Nice one! What can I clarify for you?',
                "Great! I'm here if you need anything.",
                'Happy to hear that. What can I help you with?',
                "That's a good place to be. Ask away!"],
 'mood_unhappy': ["Sorry you're having a rough time. What can I help with?",
                  "Ah, sorry to hear that. Want to tell me what's going on?",
                  "That sounds like a difficult day. I'm here if you need help with something.",
                  "Sorry things aren't going great right now. What do you need?",
                  "I hear you. If there's something I can help make easier, let me know.",
                  "That doesn't sound easy. What can I help you sort out?",
                  "Sorry you're feeling down. I'm here to help however I can.",
                  'Rough day? I hope things ease up soon.',
                  "I'm sorry. If you want to focus on an NYSC question, we can work through it "
                  'together.',
                  'That sounds tough. What would be most useful right now?',
                  "Sorry you're dealing with that. I'm listening.",
                  'Hope things get a little better. What can I help you with?'],
 'mood_bored': ['Bored, huh? We can talk NYSC if you want.',
                'Nothing to do? Throw an NYSC question at me.',
                'I get it. Want to ask me something random about NYSC?',
                "Bored already? Let's find you something useful to figure out.",
                'Sounds like you need something to do. What are you curious about?',
                "Fair enough. Got an NYSC question you've been putting off?",
                'We can kill a little time — ask me anything NYSC-related.',
                "Long day? Give me a question and let's work through it.",
                "Nothing happening? I'm here. What's on your mind?",
                'Need a distraction? I can at least help with an NYSC question.',
                "Okay, let's make the boredom productive. What do you want to know?",
                'Boredom noted. What NYSC topic should we tackle?'],
 'mood_excited': ["Love the energy! What's got you excited?",
                  'Nice! Sounds like something good happened.',
                  "That's exciting! Want to tell me about it?",
                  "Let's go! What are you excited about?",
                  'Okay, I see the energy 😄 What happened?',
                  "That's great! What can I help you with?",
                  "Love that for you. What's going on?",
                  "You're excited — I like it. What's the news?",
                  "Nice! Tell me what's got you hyped.",
                  "That's the spirit! What are we working on?",
                  'Sounds exciting! How can I help?',
                  "Good vibes. What's on your mind?"],
 'bot_identity': ["I'm Koppal. Think of me as the friend who already read every NYSC FAQ so you don't have to.",
                  "Name's Koppal. I turn 'wait, how does NYSC work again?' into a straight answer.",
                  "I'm Koppal, built for one job: making NYSC less confusing. What do you need?",
                  "Koppal here. If it's NYSC-related, I've probably got you covered — ask away.",
                  "I'm Koppal, your shortcut past the NYSC grapevine and into actual answers.",
                  "Call me Koppal. I don't do small talk about NYSC — I do straight answers.",
                  "I'm Koppal. You can call me the NYSC assistant if that's easier.",
                  "Koppal, at your service — think of me as your NYSC guide in chatbot form.",
                  "I'm Koppal, an NYSC-focused assistant. No fancy title beyond that.",
                  "I go by Koppal. I'm here specifically for NYSC questions.",
                  "I'm Koppal — the bot handling NYSC questions in this chat, nothing more mysterious than that.",
                  "Koppal's the name. Ask me anything NYSC-related."],
 'ask_ishuman': ["No — I'm a chatbot, not a human.",
                 "I'm not human. I'm an AI assistant built for NYSC questions.",
                 "Nope, I'm a bot.",
                 "I'm software, not a person — but I can still help.",
                 "I'm an AI assistant, so no human here.",
                 "No, I'm automated. What can I help you with?",
                 "Not human — I'm the chatbot handling NYSC questions.",
                 "I'm a bot, not a real person.",
                 "Nope. I'm an AI assistant for NYSC information.",
                 "I'm definitely on the chatbot side of that question 😄.",
                 "No, I'm not human. I'm here to help with NYSC information.",
                 "I'm an automated assistant rather than a person."],
 'ask_creator': ["I was built by researching NYSC's official sources directly, cross-checking every answer against them, then training a model on that verified content.",
                 "I was put together by sourcing real NYSC information, checking it for accuracy, and building the answers from that — not guessing.",
                 "I was built through actual research into NYSC's official policies and processes, verified carefully, then trained into this assistant.",
                 "A student developer built me as a capstone project, with a genuine interest in AI/ML behind it.",
                 "Why was I built? To make NYSC info less of a headache — that's the whole point of this capstone project.",
                 "I was built by a Nigerian mechatronics engineering student, and a lot of real verification went into these answers before I ever went live.",
                 "I exist because a student wanted NYSC questions to have a straight answer instead of forum guesswork — that's the project this came out of.",
                 "I was built carefully, not thrown together — real research into NYSC's official sources, then trained into this assistant."],
 'ask_official_status': ["No, I'm not an official NYSC bot — I'm an independent assistant. That said, every answer here was carefully researched and cross-checked against real NYSC sources before going live, not thrown together.",
                          "Not official, no NYSC affiliation. But this wasn't built carelessly — the info behind it was verified properly. For anything official, still go through nysc.gov.ng or portal.nysc.org.ng directly.",
                          "I'm independent, not NYSC-run, though a lot of care went into getting the answers right. Treat me as a well-researched helper, not the official source.",
                          "No NYSC affiliation here — I'm independent. Official stuff still goes through the real NYSC portal, but the info I give you was properly sourced, not guessed.",
                          "I'm not run by NYSC, just built to help with NYSC questions. Everything in here was checked against real sources first though."],
 'ask_howold': ["I don't have an age in the human sense.",
                "Age doesn't really apply to me — I'm a chatbot.",
                "I don't have a birthday or a human age.",
                "I'm not sure you'd count chatbot years 😄.",
                "I don't have an age like a person does.",
                "I'm software, so I don't really have a human age.",
                'No birthday for me — just updates and maintenance.',
                "I don't keep an age the way people do.",
                "Let's just say I'm outside the normal age system.",
                "I don't have a personal age, but I can help with NYSC questions.",
                "Human birthdays don't really apply to me.",
                "I don't age like a person does."],
 'ask_wherefrom': ["I don't have a hometown — I'm software.",
                   "I don't come from a physical place.",
                   "I'm not from anywhere in particular; I run as software.",
                   "No hometown for me. I'm just the assistant in this chat.",
                   "I don't have a birthplace the way a person does.",
                   "I'm not tied to a physical location.",
                   'I exist wherever this service is running.',
                   "I don't have a country or hometown of my own.",
                   "I'm software, so 'where are you from?' works a little differently for me.",
                   "I don't have a physical origin I can point to.",
                   'No hometown here — just an NYSC assistant.',
                   "I'm not from a particular place, but I'm here to help."],
 'ask_languagesbot': ['I mainly handle questions in English.',
                      "English is the language I'm set up to use here.",
                      'I can understand and respond to English questions.',
                      "I'm primarily designed for English-language NYSC questions.",
                      'You can ask me your NYSC questions in English.',
                      'My main language in this chat is English.',
                      'I work best with English in this NYSC assistant.',
                      'English is my main supported language here.',
                      "You can phrase your question naturally in English and I'll do my best.",
                      "I'm set up primarily for English-language conversations.",
                      'I understand common variations of English questions.',
                      'English is the safest choice for getting the clearest response from me.'],
 'bot_capability': ['I can help with NYSC questions about registration, deployment, camp, PPA, '
                    'allowances, relocation, clearance and more.',
                    'Ask me about NYSC registration, camp, PPA, deployment, allowances or '
                    'relocation.',
                    'I can explain common NYSC processes and requirements.',
                    'My focus is NYSC — from registration and deployment to camp and clearance.',
                    'You can ask me about camp, PPA, allowances, relocation, registration and '
                    'other NYSC topics.',
                    'I can help you understand common NYSC procedures and requirements.',
                    'I cover a range of NYSC topics, including registration, deployment, PPA and '
                    'allowances.',
                    "Give me an NYSC question and I'll try to point you to the relevant "
                    'information.',
                    'I can walk you through many common NYSC questions step by step.',
                    "I'm mainly useful for finding and explaining NYSC information.",
                    'I handle common questions about the service year, including camp and PPA '
                    'matters.',
                    "Ask away — if it's NYSC-related, there's a good chance I can help.",
                    'Registration, deployment, camp, PPA, allowances, relocation — those are all '
                    'within my lane.'],
 'affirmation': ['Got it.',
                 'Alright.',
                 'Okay, noted.',
                 'Sounds good.',
                 'Understood.',
                 'Okay!',
                 'Got it, thanks.',
                 'Noted.',
                 'Alright, got it.',
                 'Okay, sounds good.',
                 'Sure.',
                 'Alright, understood.'],
 'affirm_standalone': ['Okay — yes to what exactly?',
                       'Got you, but what are you saying yes to?',
                       'Alright. What are you confirming?',
                       'Okay! Which part are you agreeing to?',
                       'Yes, I got that — what does the yes refer to?',
                       'Got it. What question is that answering?',
                       "Alright — remind me what you're confirming.",
                       'Okay, but I need a little context. Yes to which part?',
                       'Understood. What exactly are you agreeing to?',
                       'Sure — what are you saying yes to?',
                       'Okay, noted. What does the yes refer to?',
                       'I hear you. What are you confirming?'],
 'deny_standalone': ['Okay — no to what exactly?',
                     'Got it. What are you saying no to?',
                     'Alright — which part are you declining?',
                     'Okay, but what does the no refer to?',
                     'Understood. What question is that answering?',
                     'Got you. No to which part?',
                     "Alright, remind me what you're responding to.",
                     'Okay — what exactly are you saying no to?',
                     'Noted. What are you declining?',
                     'Sure. What does the no refer to?',
                     'I hear you. Which option are you rejecting?',
                     'Okay. Give me a little context on the no.'],
 'compliment': ['Thank you! Glad I could help.',
                "That's kind of you to say.",
                'Appreciate that!',
                'Thanks! Happy to help.',
                'Glad you think so!',
                'Thank you — I appreciate it.',
                "That's nice to hear. What else can I help with?",
                "Thanks! I'm glad the answer was useful.",
                'Appreciate the kind words.',
                'Thank you! Ask me anything else you need.',
                "You're making the bot feel useful 😄. What can I help with next?",
                'Thanks! Glad I could be of help.'],
 'frustration': ["Sorry about that. Tell me what you were trying to find, and I'll try again.",
                 'I understand. Let me take another shot — what exactly do you need?',
                 'Sorry, I missed the mark there. Can you rephrase it?',
                 "That's frustrating. Tell me where the answer went wrong.",
                 "Apologies. Give me the question again and I'll try to answer it more clearly.",
                 "I hear you. Let's start again — what are you trying to find out?",
                 'Sorry about the confusion. What part do you need help with?',
                 "You're right to flag that. Tell me what you expected me to answer.",
                 "Sorry, that wasn't useful. Let me try a different approach.",
                 "I get why you're annoyed. What exactly should I clarify?",
                 "My bad. Send the question again and I'll focus on the specific thing you need.",
                 "Sorry about that — let's reset and try it again."],
 'small_talk': ["Just here and ready to help. What's up?",
                'Nothing much on my side — what are you thinking about?',
                "Just doing my chatbot thing 😄. What's on your mind?",
                'All quiet here. What do you need?',
                "I'm here. Got anything you want to ask?",
                'Just waiting for your next question.',
                'Not much happening on my end. What can I help with?',
                "I'm around! What's up?",
                'Just here answering questions. What are you working on?',
                'All good here. What would you like to talk about?',
                'Nothing new on my side — go ahead.',
                'Just hanging around in chatbot land. What do you need?'],
 'laughter': ["Haha 😄. What's up?",
              '😂 Glad that got a laugh.',
              'Haha, alright! What can I help with?',
              'Okay, you got me 😄.',
              "Lol! What's on your mind?",
              '😂 Fair enough. What do you need?',
              "Haha! Go on, I'm listening.",
              "That got me too 😄. What's the question?",
              'Okayyy 😂. What can I help you with?',
              'Haha, alright — ask away.',
              '😂 Nice one. What are we doing next?',
              "Glad we're having a little fun. What's up?"],
 'filler': ['Take your time.',
            "No rush — I'm here.",
            "Sure, whenever you're ready.",
            "Take a moment. I'll be here.",
            "No problem. Go ahead when you're ready.",
            "That's fine — take your time.",
            "Whenever you're ready, send it through.",
            "No pressure. I'm listening.",
            'Sure. Take a second and think it through.',
            "All good — I'm here when you're ready.",
            'Take your time, no worries.',
            'Ready when you are.'],
 'confusion_from_user': ['No worries — what part is unclear?',
                         "Tell me which part confused you and I'll explain it differently.",
                         "That's okay. Where exactly are you stuck?",
                         'No problem. What should I break down?',
                         'Which part would you like me to explain again?',
                         "Let me know what didn't make sense.",
                         "That's alright — point me to the confusing part.",
                         'No worries. I can explain it another way.',
                         "Where did I lose you? Tell me the part that's unclear.",
                         "Okay, let's slow it down. What part needs clarification?",
                         "Tell me what you understood so far and I'll fill in the gap.",
                         'No problem — what exactly is confusing you?'],
 'apology_from_user': ['No need to apologize.',
                       "You're fine — go ahead.",
                       'No worries at all.',
                       "It's okay. What do you need?",
                       "You're good. Ask away.",
                       'No problem — take your time.',
                       "That's completely fine.",
                       "It's all good. What's your question?",
                       'No need to say sorry — just continue.',
                       "You're okay. What can I help with?",
                       "Don't worry about it.",
                       'All good. Go ahead.'],
 'ask_whatismyname': ["I don't have your name unless you've told me in this conversation.",
                      "I can't reliably tell you your name from what I have here.",
                      "I don't know your name unless you've shared it with me.",
                      "I don't want to guess your name. If you tell me, I can use it in the "
                      'conversation.',
                      "I don't have your name available right now.",
                      "I can't identify you by name unless you've provided it.",
                      "Your name isn't something I can safely guess.",
                      "I don't know what you go by yet.",
                      "I'd rather not make up a name for you — you can tell me what you'd like to "
                      'be called.',
                      "I don't have a confirmed name for you.",
                      "If you haven't told me your name, I can't know it reliably.",
                      "I don't have enough information to tell you your name."],
 'ask_whoami': ["I can't determine who you are just from the chat.",
                "I don't know your identity unless you've shared relevant information.",
                "I can't identify you as a person from here.",
                'I only know what you choose to tell me in the conversation.',
                "I can't reliably tell who you are beyond what you've shared.",
                "I don't have a way to verify your identity.",
                "I wouldn't want to guess who you are.",
                'I only work with the information available in the conversation.',
                "I can't identify you by name or real-world identity from here.",
                "I don't have access to a personal identity profile for you.",
                "I can respond to what you tell me, but I can't independently identify you.",
                "I don't know who you are unless you've told me."],
 'ask_about_user': ["I don't have access to personal details about you unless you've shared them "
                    'here.',
                    "I only know the information you've chosen to provide in the conversation.",
                    "I can't reliably infer personal details about you.",
                    "I don't have a personal profile of you that I can inspect.",
                    "I don't want to guess personal information about you.",
                    "I can use details you tell me in the conversation, but I can't invent or "
                    'verify them.',
                    "I don't have access to private information about you.",
                    'I only work with the information available to me in this chat.',
                    "I can't tell personal details about you that you haven't shared.",
                    "Your private information isn't something I can simply look up.",
                    "I don't know personal facts about you unless you've provided them.",
                    "I can help with what you tell me, but I can't independently identify personal "
                    'details.'],
 'out_of_scope': ["That's outside what I can help with. I'm focused on NYSC questions.",
                  "I don't cover that topic, but I can help with NYSC-related questions.",
                  "That's outside my area. Try me with an NYSC question.",
                  "I don't have information on that. I can help with NYSC instead.",
                  "My focus is NYSC, so I can't reliably answer that one.",
                  "That's beyond the scope of this assistant. What NYSC question do you have?",
                  "I can't help with that topic, but I'm happy to handle NYSC questions.",
                  "That's not something this bot is set up to answer.",
                  'I specialize in NYSC information, so that one is outside my lane.',
                  "I don't have enough information to answer that. Ask me something about NYSC.",
                  "That's outside my scope for now. What can I help you with on NYSC?",
                  'I can help with NYSC topics, but not that one.',
                  "I only answer NYSC questions. What NYSC-related question do you have today?",
                  "I'm built specifically for NYSC, so let's keep it to that. What do you need help with?",
                  "I can't go there, but I'm all ears for anything NYSC-related.",
                  "That's not something I can help with. Got an NYSC question for me instead?"],

 'handoff_request': ["I'm the only line here for now, but I can try to sort it directly -- what's the issue?",
                     "There's no live human handoff on this bot right now. What's the question? Let's see if I can actually help.",
                     "I can't transfer you to a person, but tell me what's going on and I'll do my best.",
                     "No live agent on this end, but I'll try to get you sorted. What do you need?",
                     "This bot doesn't connect to a human rep, but throw me the question and let's see.",
                     "I'm not able to hand you off to a person, but I'm listening. What's up?",
                     "Can't patch you through to a human here, but let's try this together. What's the issue?",
                     "No human on standby on this bot, but go ahead, tell me what you need.",
                     "I can't connect you to a live person, but I might still be able to help. What's going on?",
                     "This is bot-only for now, no live transfer. What can I help you sort?"],

 'venting_nysc': ["Yeah, NYSC can really wear you down. What part is getting to you the most?",
                  "I hear you, it's a lot. Is there something specific I can actually help sort out?",
                  "Fair, the whole process can be exhausting. What's frustrating you right now?",
                  "It's a stressful program for a lot of people, not just you. What's going on?",
                  "No wahala, I get it, it's a lot to deal with. What can I help you sort?",
                  "It really can be draining. Anything I can help make less confusing right now?",
                  "Understandable. What part of it is bothering you most?",
                  "You're not alone in feeling that way. What's the specific thing giving you trouble?",
                  "It's a tough process, fair to feel that way. What can I help clear up?",
                  "I get why it's frustrating. Is there a specific thing I can help you with?"],

 'dispute_answer': ["Okay, tell me what you heard so I can check it against what I have.",
                    "Fair enough -- what's the different info you got? I'll compare it to what I have here.",
                    "I could be wrong. What did you hear instead?",
                    "Let's check that. What's the version you were told?",
                    "Noted -- tell me what you were told and I'll see if it matches what I have.",
                    "That's possible, requirements do get updated. What did you hear?",
                    "Okay, what's the conflicting info so I can take a look?",
                    "Alright, what's different about what you heard?",
                    "Could be outdated on my end. What's the other version?",
                    "Let's compare -- what did you hear that's different?"],

 'trust_check': ["As sure as the source allows -- this is pulled from NYSC's own info, not a guess.",
                 "I'm working from NYSC-sourced info, not making it up, but always confirm anything critical with your LGI.",
                 "Reasonably confident, though I'd still double check anything urgent with your LGI directly.",
                 "I try to only answer from what's actually documented, not guesswork.",
                 "Fairly sure, but for anything with a deadline attached, confirm with your LGI too.",
                 "It's based on NYSC's own info where I have it. Still, always good to confirm officially for anything urgent.",
                 "I'm not just guessing, but I'd still verify anything time-sensitive directly.",
                 "Confident in what I said, though I'm not a replacement for confirming with your LGI on anything critical.",
                 "I stick to documented info, but double-checking urgent stuff never hurts.",
                 "As accurate as my sources allow -- always confirm anything urgent officially too."],

 'insult_abuse': ["Fair enough. I'm still here if you want to try the question again.",
                  "Noted. Let me know what you actually need and I'll try again.",
                  "Okay. If you want another shot at the question, I'm here.",
                  "Understood. What are you actually trying to find out?",
                  "Alright. Tell me the question again and I'll give it another go.",
                  "Noted, moving on -- what do you need?",
                  "Okay, let's reset. What's the actual question?",
                  "I hear you. What can I help you with?",
                  "Alright. What's the question you need answered?",
                  "Fair. Let's try again -- what do you need?"],

 'reengagement_ping': ["Still here! What do you need?",
                       "Yep, I'm here. Go ahead.",
                       "I'm here, what's up?",
                       "Still around. Ask away.",
                       "Here! What can I help with?",
                       "Yes, still listening. What's the question?",
                       "I'm here, didn't go anywhere. What do you need?",
                       "Still with you. Go ahead.",
                       "Present! What's up?",
                       "I'm here, ready when you are."],

 'ask_joke': ["I'm not really built for jokes, but I can make NYSC less confusing, which is almost as good.",
              "No joke bank on me, but I can at least make your NYSC questions less painful.",
              "I'll leave the comedy to someone else -- ask me an NYSC question, I've got that covered.",
              "Not my strong suit, but I promise NYSC answers are more useful than my jokes would be.",
              "I don't really do jokes, but I can def help you figure out NYSC stuff.",
              "Comedy isn't really in my job description -- NYSC info is though.",
              "I'd probably ruin the joke. Let's stick to NYSC questions.",
              "No jokes here, but I'm solid on NYSC info.",
              "I'll pass on the joke, but hit me with an NYSC question instead.",
              "Not a comedian, just an NYSC assistant, but I'm here if you need something real."],

 'ask_opinion': ["I don't really have preferences, I just work with NYSC info.",
                 "No favorites here, I'm just focused on giving you accurate NYSC info.",
                 "I don't have opinions like that, but I can give you the facts on NYSC.",
                 "Not really something I have a take on, but ask me something NYSC-related and I've got you.",
                 "I don't do personal opinions, just NYSC info.",
                 "Can't say I have a favorite, I just handle NYSC questions.",
                 "No real opinions on my end, I stick to NYSC facts.",
                 "I'm not really wired for opinions, just information.",
                 "Don't have a take on that, but NYSC questions I can help with.",
                 "Not something I have feelings about, I just handle NYSC info."],

 'memory_check': ["I don't hold onto anything between conversations, so tell me again and I'll work with it now.",
                  "No memory across chats on my end -- what do you need me to know for this conversation?",
                  "I don't save anything long-term, so go ahead and tell me now.",
                  "Nothing carries over once the conversation ends. What do you need?",
                  "I don't have memory beyond this chat. Tell me again if it matters.",
                  "No persistent memory here, so let me know what you need right now.",
                  "I forget everything once this chat ends. What do you need me to know?",
                  "I don't retain past conversations. Tell me fresh.",
                  "Nothing sticks around after this chat -- go ahead and tell me again.",
                  "I don't keep records between sessions. What do you need right now?"],

 'flirting': ["Ha, I'll take the compliment, but I'm just here for NYSC questions.",
              "I appreciate it, but let's keep this to NYSC business.",
              "Flattered, but I'm strictly an NYSC assistant.",
              "Ha, thanks, but I'm not really available for that -- what NYSC question do you have?",
              "I'll stick to what I'm good at, NYSC info. What do you need?",
              "Appreciate it, but I'm just a bot for NYSC questions.",
              "Ha, noted, but let's get back to NYSC stuff.",
              "I'm flattered, but strictly business here -- NYSC business.",
              "Thanks, but I'm really just here for the NYSC info. What do you need?",
              "Ha, I'll pass, but happy to help with an actual NYSC question."],

 'off_topic_smalltalk': ["Ha, can't say I feel the weather, but I hear you. Anyway, any NYSC question for me?",
                         "Not really something I experience, but go ahead -- ask me an NYSC question if you've got one.",
                         "I wouldn't know, I'm just software. What can I help with on NYSC?",
                         "Can't relate honestly, I'm indoors in every sense. Got an NYSC question?",
                         "Ha, that's outside my lane, but NYSC questions are right in it.",
                         "I don't experience that stuff, but I'm here for NYSC questions.",
                         "Not something I'd know about, but ask me something NYSC-related.",
                         "Ha, fair. Anyway, what NYSC question do you have?",
                         "I'll take your word for it. Anything NYSC-related I can help with?",
                         "Can't really comment on that, but NYSC I can help with."]}


def get_time_based_greeting_category() -> str:
    """
    Return the correct greeting category based on current Nigerian time.
    Morning: 5:00-11:59. Afternoon: 12:00-16:59. Evening: 17:00-20:59.
    Night: 21:00 onward, through to 4:59.
    """
    hour = datetime.now(TIMEZONE).hour
    if 5 <= hour < 12:
        return "greeting_morning"
    elif 12 <= hour < 17:
        return "greeting_afternoon"
    elif 17 <= hour < 21:
        return "greeting_evening"
    else:
        return "greeting_night"


def get_reply(category: str) -> str:
    """
    Return a random reply for the given chitchat category.
    If category is "greeting", automatically routes to the correct
    time-of-day variant (greeting_morning/afternoon/evening).
    Falls back to a generic response if the category is unknown.
    """
    if category == "greeting":
        category = get_time_based_greeting_category()

    replies = CHITCHAT_REPLIES.get(category)
    if not replies:
        return "I'm not sure how to respond to that, but I'm here to help with NYSC questions."
    return random.choice(replies)


# ============================================================
# NIGERIAN PIDGIN KEYWORD DETECTION
# Checked before classification, not trained via TF-IDF -- catches
# phrasings training examples would likely miss. Sourced from real
# Nigerian Pidgin usage (cross-checked across multiple sources).
# ============================================================
PIDGIN_KEYWORD_TRIGGERS = {
    "greeting": ["how far", "wetin dey happen", "wetin dey", "how you dey", "how bodi"],
    "thanks": ["tank yu", "tanks", "you do well"],
    "affirmation": ["no wahala"],
    "mood_unhappy": ["wahala dey", "wahala dey o", "i dey vex", "vex", "no stress me"],
    "how_are_you": ["how you dey", "how bodi"],
}


# ============================================================
# ENGLISH CHITCHAT KEYWORD DETECTION
# Same role as PIDGIN_KEYWORD_TRIGGERS, for standard English. Checked
# before classification (dialogue_manager step 2.5) so formulaic small
# talk never competes as a 132nd classifier class. category -> phrases,
# matched whole-word / whole-phrase, case-insensitive.
#
# First-pass keyword set. Nigerian English is a THIRD register, distinct
# from both standard English and Pidgin (e.g. "well done" used as a
# greeting, not praise), so these lists are expected to grow later
# (content review, D5) -- add the Nigerian-English phrasings then.
# ============================================================
CHITCHAT_KEYWORD_TRIGGERS = {
    "greeting": ["hi", "hello", "hey", "hiya", "good morning",
                 "good afternoon", "good evening", "greetings"],
    "farewell": ["bye", "goodbye", "good bye", "see you", "see ya",
                 "take care", "gtg"],
    "thanks": ["thanks", "thank you", "thankyou", "thanx",
               "much appreciated", "appreciate it", "cheers"],
    "how_are_you": ["how are you", "how you doing", "how's it going",
                    "hows it going", "how do you do"],
    "bot_identity": ["who are you", "what are you", "what is your name",
                     "your name"],
    "ask_ishuman": ["are you human", "are you real", "are you a bot",
                    "are you a robot"],
    "compliment": ["good job", "well done", "you are helpful",
                   "you're helpful", "nice one", "good bot", "you're the best"],
    "apology_from_user": ["sorry", "my bad", "apologies", "my apologies"],
    "laughter": ["lol", "lmao", "haha", "hahaha", "rofl"],
    "handoff_request": ["talk to a human", "speak to a human", "real person",
                        "human agent", "talk to someone real", "speak to a real person"],
    "reengagement_ping": ["are you there", "still there", "you there", "hello?"],
    "ask_joke": ["tell me a joke", "make me laugh", "say something funny",
                "know any jokes", "try making me laugh"],
    "ask_opinion": ["what do you think", "your opinion", "favorite state",
                    "do you like your job"],
    "memory_check": ["do you remember", "will you remember", "remember me"],
    "flirting": ["are you single", "marry me", "i like you", "you're cute"],
    "insult_abuse": ["you're mad", "you're a fool", "you're useless", "you're an idiot",
                     "you're wasting my time", "out of your senses", "are you mad",
                     "have you gone mad"],
    "off_topic_smalltalk": ["weather today", "football", "match today", "news today"],
    "bot_capability": ["what can you do", "how can you help me", "what is your main purpose",
                       "what kind of tasks can you handle", "tell me all the things you can do"],
    "ask_creator": ["who made you", "who built you", "who built this bot", "who's behind this",
                    "who is behind this", "why were you built"],
    "ask_official_status": ["is this official", "nysc official chatbot", "official nysc bot",
                            "are you nysc", "is this nysc program", "is this app made by nysc",
                            "does nysc know about this", "is this endorsed by nysc",
                            "are you run by nysc", "do you work for nysc"],
    "ask_howold": ["how old are you"],
    "ask_wherefrom": ["where are you from"],
    "ask_languagesbot": ["what languages", "do you speak pidgin", "do you speak yoruba",
                         "do you speak igbo", "do you speak hausa"],
    "ask_whatismyname": ["do you know my name", "guess my name", "what is my name", "what's my name"],
    "ask_whoami": ["who am i", "do you know who i am", "can you tell who i am"],
    "ask_about_user": ["what do you know about me", "you get my details", "tell me something about myself"],
    "mood_great": ["feeling really good today", "life is good right now", "today don blow for me",
                  "in a really good mood", "things are going really well for me", "in high spirits today"],
    "mood_bored": ["nothing to do sha", "boredom don catch me", "boredom wan wound me",
                   "boredom wan kpai me", "nothing dey happen today", "just sitting here with nothing to do"],
    "mood_excited": ["guess what just happened", "i'm buzzing right now", "i get correct gist for you",
                     "can't stop smiling right now", "i'm so hyped right now", "something amazing just happened"],
    "affirm_standalone": ["yes o", "ehen yes", "na so"],
    "deny_standalone": ["no o", "i no gree", "never that"],
    "confusion_from_user": ["i don't understand what you mean", "wetin you mean by that",
                            "this one no clear at all", "i'm lost, explain am small",
                            "you fit break am down", "i no understand wetin you talk"],
    "frustration": ["this isn't helping at all", "you're not understanding what i'm asking",
                    "this thing dey worry me", "i don ask this same question tire",
                    "why can't you just answer me well"],
    "small_talk": ["how market", "just checking in", "anything new today", "wetin dey happen"],
    "filler": ["hold on", "give me a second", "one moment abeg", "small time, i dey come",
              "make i check am first", "wait let me check something"],
    # venting_nysc is intentionally NOT a plain keyword entry -- see
    # _check_venting() below. A keyword hit on "stressed" would swallow a
    # real question ("I'm stressed, my Senate List won't update, what do I
    # do?"), so it needs its own gated check, not a table lookup.
    #
    # dispute_answer and trust_check are also intentionally absent here --
    # they only make sense as a reaction to something the bot just said
    # ("that's not what I heard," "are you sure?"), not as standalone
    # phrases. They're gated on ConversationState.awaiting_reaction in
    # dialogue_manager.py instead of matched here. See _check_reaction().
    #
    # self_correction was considered and dropped. The common case (fixing
    # an answer to a still-pending slot) is already handled for free by
    # the pending-slot re-check in dialogue_manager.py step 1. Correcting
    # a slot the flow has already moved past was explicitly deferred at
    # the architecture stage as low-value for an FAQ bot. Nothing left
    # for this category to cover.
}

VENTING_NYSC_PHRASES = ["stressed", "stressing", "wahala", "tired of this",
                        "exhausted", "draining", "wearing me out", "worn out"]
REACTION_PHRASES = {
    "dispute_answer": ["that's not what i heard", "that's not what i know",
                       "that's not how it is", "that's not how it's done",
                       "you don't know what you're saying", "that's not what i was told",
                       "that doesn't sound right", "i heard something different"],
    "trust_check": ["how sure are you", "is this accurate", "are you certain",
                    "can i trust this", "is this reliable", "do you know what you're saying",
                    "hope you know what you're saying", "did you confirm this"],
}

# Openers double as polite prefixes to real questions ("hi, how do I fix X?"),
# so they only fire on SHORT messages; longer ones fall through to the
# classifier even if they contain the keyword. First-pass value -- tune later.
CHITCHAT_OPENER_MAX_WORDS = 5
_OPENER_CATEGORIES = {"greeting", "farewell", "apology_from_user"}


def _check_venting(message: str) -> bool:
    """
    venting_nysc gate: only fires on short messages with no question mark,
    same logic as _OPENER_CATEGORIES, so a real embedded question ("I'm so
    stressed, my Senate List won't update, what do I do?") falls through to
    the classifier instead of being swallowed by the venting reply.
    """
    msg = message.strip().lower()
    if "?" in msg:
        return False
    if len(msg.split()) > CHITCHAT_OPENER_MAX_WORDS + 3:  # slightly more room than greetings
        return False
    return any(re.search(r"\b" + re.escape(p) + r"\b", msg) for p in VENTING_NYSC_PHRASES)


def check_reaction(message: str, awaiting_reaction: bool):
    """
    dispute_answer / trust_check gate. Only checked when the caller
    (dialogue_manager.py) says the last turn was a real KB answer, i.e.
    state.awaiting_reaction is True. Outside that window these phrases are
    just as likely to be a fresh, unrelated question and shouldn't be
    swallowed as a reaction to nothing.
    """
    if not awaiting_reaction:
        return None
    msg = message.strip().lower()
    for category, phrases in REACTION_PHRASES.items():
        for phrase in phrases:
            if phrase in msg:
                return category
    return None


def detect_chitchat(message: str):
    """
    Pre-classifier chitchat detection (dialogue_manager step 2.5).
    Return the matching chitchat CATEGORY for formulaic small talk, or
    None if the message isn't chitchat (caller then classifies normally).
    Pidgin triggers checked first, then English. Openers only fire on
    short messages so greeting-prefixed real questions still get classified.
    Note: dispute_answer/trust_check are NOT checked here -- call
    check_reaction() separately with state.awaiting_reaction. This function
    only covers context-free categories.
    """
    msg = message.strip().lower()
    if not msg:
        return None
    word_count = len(msg.split())
    for table in (PIDGIN_KEYWORD_TRIGGERS, CHITCHAT_KEYWORD_TRIGGERS):
        for category, phrases in table.items():
            for phrase in phrases:
                if re.search(r"\b" + re.escape(phrase) + r"\b", msg):
                    if category in _OPENER_CATEGORIES and word_count > CHITCHAT_OPENER_MAX_WORDS:
                        continue
                    return category
    if _check_venting(message):
        return "venting_nysc"
    return None


# ============================================================
# DISMISSAL OF AN OPEN FOLLOW-UP
# A user's way OUT of a pending question -- "never mind", "forget it",
# "no worry, i've gotten that", "okay". dialogue_manager checks this
# BEFORE the pending-slot logic, so a dismissal always clears the
# follow-up instead of being read as a slot answer or dead-ending in
# noise with the chips still up. BROAD set (owner's call): plain
# acknowledgements count too.
#
# Two tiers, so the generic acks can't swallow a real question:
#   DISMISSAL_TRIGGERS -- multi-word phrases; matched as a whole word
#     anywhere inside a SHORT message ("no worry, i have gotten that").
#   DISMISSAL_EXACT    -- bare acks ("ok", "got it"); only fire when they
#     are essentially the WHOLE message, so "ok when do i get paid" is
#     still answered normally rather than dismissed.
# ============================================================
DISMISSAL_MAX_WORDS = 6

DISMISSAL_TRIGGERS = [
    "never mind", "nevermind",
    "forget it", "forget that", "forget about it",
    "drop it", "leave it",
    "no worry", "no worries",
    "i have gotten that", "i've gotten that",
    "i have got that", "i've got that",
    "i have gotten it", "i've gotten it", "gotten it",
    "that's all", "thats all",
    "thanks that's all", "thanks thats all", "thank you that's all",
]

DISMISSAL_EXACT = [
    "ok", "okay", "ok then", "okay then",
    "got it", "i got it",
    "ok thanks", "okay thanks",
]


def is_dismissal(message: str) -> bool:
    """
    True when the message is a short ack/dismissal of an open follow-up
    ("never mind", "no worry, i have gotten that", "okay"). Kept short so
    the words can't misfire inside a real question; bare acks must be the
    whole message. Broad set: plain acknowledgements count (owner's call).
    """
    msg = message.strip().lower()
    if not msg:
        return False
    if msg.strip(" .!,") in DISMISSAL_EXACT:
        return True
    if len(msg.split()) > DISMISSAL_MAX_WORDS:
        return False
    for phrase in DISMISSAL_TRIGGERS:
        if re.search(r"\b" + re.escape(phrase) + r"\b", msg):
            return True
    return False


# ============================================================
# STRESS-FLAGGED INTENTS (topic-based empathy, distinct from
# mood_unhappy above -- that's about the USER's stated mood;
# this is about the SUBJECT MATTER of the KB intent itself.
# This is the PRIMARY/default tone whenever one of these intents
# is active, taking priority over any CASUAL/CHITCHAT_REPLIES
# category -- see chatbot_architecture_v2.md Section 5.
# ============================================================
STRESS_FLAGGED_INTENTS = {
    "ppa_rejection_reposting",
    "disciplinary_query",
    "relocation_consequences",
    "clearance_ppa_wont_sign",
    "missed_posting_consequence",
    "consequence_of_not_reporting",
    "remobilization_after_abandon",
    "certificate_correction_pending",
}

EMPATHETIC_OPENERS = [
    "That's a genuinely stressful situation -- let's get this sorted.",
    "I understand this is worrying. Here's what you can actually do about it:",
    "Okay, let's work through this calmly -- here's where things stand:",
    "I hear you -- this is fixable. Here's how:",
]

EMPATHETIC_DELIVERY = [
    "I won't sugarcoat this, but here's the reality:",
    "This part isn't the news you want, but it's better to know clearly:",
]


# ============================================================
# PENDING-SLOT REPLY LISTS
# Referenced by dialogue_manager.py on the fuzzy-confirm and
# low-confidence-while-pending paths. Kept here (canned phrasing),
# not in the KB (NYSC content only).
# ============================================================

# Shown when a fuzzy (not exact) match is found on a pending slot value,
# to confirm before filling. {match} = the candidate option.
CONFIRM_MATCH = [
    "Just to confirm -- did you mean {match}?",
    "Do you mean {match}?",
    "Got it -- {match}, is that right?",
    "Sounds like {match} -- is that what you meant?",
]

# Shown on a low-confidence message WHILE a slot question is still pending,
# to steer the user back. {pending_question} = the pending question text.
FALLBACK_PENDING = [
    "I didn't quite catch that. To continue: {pending_question}",
    "Sorry, I'm not sure I follow. {pending_question}",
    "Let's stay on track -- {pending_question}",
]

# Shown when the classifier routes a message to `noise` (gibberish /
# not-a-question / clearly-not-NYSC). Distinct from out_of_scope, which is
# a coherent off-topic question.
NOISE_FALLBACK = [
    "I didn't quite catch that -- could you rephrase? I answer NYSC questions.",
    "Sorry, I'm not sure what you mean. Ask me anything about NYSC.",
    "Hmm, that didn't come through clearly. What NYSC question can I help with?",
]

# Brief, warm acknowledgement when a user dismisses an open follow-up
# ("never mind", "got it"). We drop the pending question and say a light
# okay -- no re-prompt, no chips.
DISMISSAL_ACK = [
    "No problem. Ask me anything else about NYSC whenever you're ready.",
    "Sure thing -- I'm here whenever another NYSC question comes up.",
    "Alright! Ask away whenever you need anything NYSC-related.",
    "Okay -- no worries. What else can I help you with?",
]

# Re-surface an open follow-up ONCE after a greeting/thanks, worded as a
# natural line rather than pasting the raw question onto the reply. Shown a
# single time per open follow-up (dialogue_manager tracks pending_reminded);
# a second greeting just greets. {pending_question} = the pending text.
PENDING_NUDGE = [
    "Whenever you're ready: {pending_question}",
    "Still on that when you are -- {pending_question}",
    "No rush -- when you're set: {pending_question}",
]
